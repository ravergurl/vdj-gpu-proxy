#include "http_client.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <mutex>
#include <sstream>
#include <algorithm>
#include <cstring>

#pragma comment(lib, "winhttp.lib")

namespace vdj {

namespace {
    constexpr DWORD CONNECT_TIMEOUT_MS = 10000;
    constexpr DWORD REQUEST_TIMEOUT_MS = 60000;

    // Simple base64 encoding
    static const char base64_chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    std::string Base64Encode(const uint8_t* data, size_t len) {
        std::string result;
        result.reserve(((len + 2) / 3) * 4);

        for (size_t i = 0; i < len; i += 3) {
            uint32_t val = (data[i] << 16);
            if (i + 1 < len) val |= (data[i + 1] << 8);
            if (i + 2 < len) val |= data[i + 2];

            result += base64_chars[(val >> 18) & 0x3F];
            result += base64_chars[(val >> 12) & 0x3F];
            result += (i + 1 < len) ? base64_chars[(val >> 6) & 0x3F] : '=';
            result += (i + 2 < len) ? base64_chars[val & 0x3F] : '=';
        }
        return result;
    }

    int Base64DecodeChar(char c) {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;
    }

    std::vector<uint8_t> Base64Decode(const std::string& input) {
        std::vector<uint8_t> result;
        result.reserve((input.size() * 3) / 4);

        int val = 0, bits = -8;
        for (char c : input) {
            if (c == '=') break;
            int d = Base64DecodeChar(c);
            if (d < 0) continue;
            val = (val << 6) | d;
            bits += 6;
            if (bits >= 0) {
                result.push_back((val >> bits) & 0xFF);
                bits -= 8;
            }
        }
        return result;
    }

    // Simple JSON parser helpers (no external deps)
    std::string JsonEscape(const std::string& s) {
        std::string out;
        for (char c : s) {
            switch (c) {
                case '"': out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\r': out += "\\r"; break;
                case '\t': out += "\\t"; break;
                default: out += c;
            }
        }
        return out;
    }

    // Extract JSON string value
    std::string JsonGetString(const std::string& json, const std::string& key) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return "";

        pos = json.find(':', pos);
        if (pos == std::string::npos) return "";

        pos = json.find('"', pos);
        if (pos == std::string::npos) return "";
        pos++;

        size_t end = pos;
        while (end < json.size() && json[end] != '"') {
            if (json[end] == '\\') end++;
            end++;
        }
        return json.substr(pos, end - pos);
    }

    // Extract JSON boolean value
    bool JsonGetBool(const std::string& json, const std::string& key, bool defaultVal = false) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return defaultVal;

        pos = json.find(':', pos);
        if (pos == std::string::npos) return defaultVal;

        while (pos < json.size() && (json[pos] == ':' || json[pos] == ' ')) pos++;
        if (pos >= json.size()) return defaultVal;

        if (json.substr(pos, 4) == "true") return true;
        if (json.substr(pos, 5) == "false") return false;
        return defaultVal;
    }

    // Extract JSON integer value
    int64_t JsonGetInt(const std::string& json, const std::string& key, int64_t defaultVal = 0) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return defaultVal;

        pos = json.find(':', pos);
        if (pos == std::string::npos) return defaultVal;

        while (pos < json.size() && (json[pos] == ':' || json[pos] == ' ')) pos++;
        if (pos >= json.size()) return defaultVal;

        return std::stoll(json.substr(pos));
    }

    // Extract JSON array of integers
    std::vector<int64_t> JsonGetIntArray(const std::string& json, const std::string& key) {
        std::vector<int64_t> result;
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return result;

        pos = json.find('[', pos);
        if (pos == std::string::npos) return result;
        pos++;

        size_t end = json.find(']', pos);
        if (end == std::string::npos) return result;

        std::string arr = json.substr(pos, end - pos);
        std::stringstream ss(arr);
        std::string item;
        while (std::getline(ss, item, ',')) {
            try {
                result.push_back(std::stoll(item));
            } catch (...) {}
        }
        return result;
    }

    std::wstring Utf8ToWide(const std::string& str) {
        if (str.empty()) return L"";
        int size = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), nullptr, 0);
        std::wstring result(size, 0);
        MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), &result[0], size);
        return result;
    }
}

class HttpClient::Impl {
public:
    HINTERNET hSession = nullptr;
    HINTERNET hConnect = nullptr;
    std::wstring host;
    INTERNET_PORT port = INTERNET_DEFAULT_HTTPS_PORT;
    bool useSSL = true;
    bool connected = false;
    mutable std::mutex mutex;

    ~Impl() {
        if (hConnect) WinHttpCloseHandle(hConnect);
        if (hSession) WinHttpCloseHandle(hSession);
    }

    std::string DoRequest(const wchar_t* method, const std::wstring& path,
                         const std::string& body, const wchar_t* contentType) {
        if (!hConnect) return "";

        DWORD flags = useSSL ? WINHTTP_FLAG_SECURE : 0;
        HINTERNET hRequest = WinHttpOpenRequest(
            hConnect, method, path.c_str(), nullptr,
            WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags
        );
        if (!hRequest) return "";

        // Set timeouts
        WinHttpSetTimeouts(hRequest, REQUEST_TIMEOUT_MS, CONNECT_TIMEOUT_MS,
                          REQUEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS);

        // Set headers
        std::wstring headers;
        if (contentType) {
            headers = L"Content-Type: ";
            headers += contentType;
        }

        // Ignore SSL cert errors for testing (TODO: make configurable)
        DWORD secFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                        SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                        SECURITY_FLAG_IGNORE_CERT_CN_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &secFlags, sizeof(secFlags));

        BOOL result = WinHttpSendRequest(
            hRequest,
            headers.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : headers.c_str(),
            headers.empty() ? 0 : (DWORD)-1,
            body.empty() ? WINHTTP_NO_REQUEST_DATA : (LPVOID)body.c_str(),
            (DWORD)body.size(),
            (DWORD)body.size(),
            0
        );

        if (!result) {
            WinHttpCloseHandle(hRequest);
            return "";
        }

        if (!WinHttpReceiveResponse(hRequest, nullptr)) {
            WinHttpCloseHandle(hRequest);
            return "";
        }

        // Read response
        std::string response;
        DWORD bytesRead = 0;
        char buffer[8192];

        while (WinHttpReadData(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
            response.append(buffer, bytesRead);
        }

        WinHttpCloseHandle(hRequest);
        return response;
    }
};

HttpClient::HttpClient() : impl_(std::make_unique<Impl>()) {}
HttpClient::~HttpClient() = default;

bool HttpClient::Connect(const std::string& base_url) {
    std::lock_guard<std::mutex> lock(impl_->mutex);

    // Parse URL
    std::string url = base_url;
    impl_->useSSL = true;
    impl_->port = INTERNET_DEFAULT_HTTPS_PORT;

    if (url.find("https://") == 0) {
        url = url.substr(8);
    } else if (url.find("http://") == 0) {
        url = url.substr(7);
        impl_->useSSL = false;
        impl_->port = INTERNET_DEFAULT_HTTP_PORT;
    }

    // Remove trailing slash
    while (!url.empty() && url.back() == '/') url.pop_back();

    // Check for port
    size_t colonPos = url.find(':');
    if (colonPos != std::string::npos) {
        impl_->port = (INTERNET_PORT)std::stoi(url.substr(colonPos + 1));
        url = url.substr(0, colonPos);
    }

    impl_->host = Utf8ToWide(url);

    // Create session
    impl_->hSession = WinHttpOpen(
        L"VDJ-GPU-Proxy/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );
    if (!impl_->hSession) return false;

    // Set timeouts
    WinHttpSetTimeouts(impl_->hSession, CONNECT_TIMEOUT_MS, CONNECT_TIMEOUT_MS,
                      REQUEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS);

    // Connect
    impl_->hConnect = WinHttpConnect(impl_->hSession, impl_->host.c_str(), impl_->port, 0);
    if (!impl_->hConnect) {
        WinHttpCloseHandle(impl_->hSession);
        impl_->hSession = nullptr;
        return false;
    }

    // Test connection with health check
    std::string response = impl_->DoRequest(L"GET", L"/health", "", nullptr);
    impl_->connected = (response.find("\"status\"") != std::string::npos);

    if (!impl_->connected) {
        OutputDebugStringA("VDJ-GPU-Proxy: HTTP health check failed\n");
        OutputDebugStringA(response.c_str());
    }

    return impl_->connected;
}

void HttpClient::Disconnect() {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    if (impl_->hConnect) {
        WinHttpCloseHandle(impl_->hConnect);
        impl_->hConnect = nullptr;
    }
    if (impl_->hSession) {
        WinHttpCloseHandle(impl_->hSession);
        impl_->hSession = nullptr;
    }
    impl_->connected = false;
}

bool HttpClient::IsConnected() const {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    return impl_->connected;
}

ServerInfo HttpClient::GetServerInfo() {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    ServerInfo info = {};

    std::string response = impl_->DoRequest(L"GET", L"/info", "", nullptr);
    if (response.empty()) return info;

    info.version = JsonGetString(response, "version");
    info.model_name = JsonGetString(response, "model_name");
    info.ready = JsonGetBool(response, "ready");
    info.max_batch_size = (int)JsonGetInt(response, "max_batch_size");

    return info;
}

HttpInferenceResult HttpClient::RunInference(
    uint64_t session_id,
    const std::vector<std::string>& input_names,
    const std::vector<HttpTensorData>& inputs,
    const std::vector<std::string>& output_names
) {
    HttpInferenceResult result;
    result.success = false;

    if (input_names.size() != inputs.size()) {
        result.error_message = "Input names count does not match inputs count";
        return result;
    }

    std::lock_guard<std::mutex> lock(impl_->mutex);

    if (!impl_->connected || !impl_->hConnect) {
        result.error_message = "Not connected to server";
        return result;
    }

    // Build JSON request
    std::stringstream json;
    json << "{\"session_id\":" << session_id << ",";
    json << "\"input_names\":[";
    for (size_t i = 0; i < input_names.size(); i++) {
        if (i > 0) json << ",";
        json << "\"" << JsonEscape(input_names[i]) << "\"";
    }
    json << "],\"inputs\":[";

    for (size_t i = 0; i < inputs.size(); i++) {
        if (i > 0) json << ",";
        json << "{\"shape\":[";
        for (size_t j = 0; j < inputs[i].shape.size(); j++) {
            if (j > 0) json << ",";
            json << inputs[i].shape[j];
        }
        json << "],\"dtype\":" << inputs[i].dtype << ",";
        json << "\"data\":\"" << Base64Encode(inputs[i].data.data(), inputs[i].data.size()) << "\"}";
    }

    json << "],\"output_names\":[";
    for (size_t i = 0; i < output_names.size(); i++) {
        if (i > 0) json << ",";
        json << "\"" << JsonEscape(output_names[i]) << "\"";
    }
    json << "]}";

    std::string body = json.str();
    std::string response = impl_->DoRequest(L"POST", L"/inference", body, L"application/json");

    if (response.empty()) {
        result.error_message = "Empty response from server";
        return result;
    }

    // Check for error
    if (response.find("\"error\"") != std::string::npos ||
        response.find("\"detail\"") != std::string::npos) {
        result.error_message = JsonGetString(response, "error");
        if (result.error_message.empty()) {
            result.error_message = JsonGetString(response, "detail");
        }
        return result;
    }

    // Parse outputs array
    // Find "outputs": [ ... ]
    size_t outputsStart = response.find("\"outputs\"");
    if (outputsStart == std::string::npos) {
        result.error_message = "No outputs in response";
        return result;
    }

    size_t arrayStart = response.find('[', outputsStart);
    if (arrayStart == std::string::npos) {
        result.error_message = "Invalid outputs format";
        return result;
    }

    // Parse each output tensor
    size_t pos = arrayStart + 1;
    while (pos < response.size()) {
        size_t objStart = response.find('{', pos);
        if (objStart == std::string::npos) break;

        size_t objEnd = response.find('}', objStart);
        if (objEnd == std::string::npos) break;

        std::string tensorJson = response.substr(objStart, objEnd - objStart + 1);

        HttpTensorData td;
        td.shape = JsonGetIntArray(tensorJson, "shape");
        td.dtype = (int32_t)JsonGetInt(tensorJson, "dtype");
        std::string dataStr = JsonGetString(tensorJson, "data");
        td.data = Base64Decode(dataStr);

        result.outputs.push_back(std::move(td));

        pos = objEnd + 1;
        // Skip to next { or break if ]
        while (pos < response.size() && response[pos] != '{' && response[pos] != ']') pos++;
        if (pos >= response.size() || response[pos] == ']') break;
    }

    result.success = true;
    return result;
}

HttpInferenceResult HttpClient::RunInferenceBinary(
    uint64_t session_id,
    const std::vector<std::string>& input_names,
    const std::vector<HttpTensorData>& inputs,
    const std::vector<std::string>& output_names
) {
    // For now, fall back to JSON. Binary requires protobuf serialization.
    // TODO: Implement binary protobuf for better performance
    return RunInference(session_id, input_names, inputs, output_names);
}

static std::unique_ptr<HttpClient> g_httpClient;
static std::once_flag g_httpClientInit;

HttpClient* GetHttpClient() {
    std::call_once(g_httpClientInit, []() {
        g_httpClient = std::make_unique<HttpClient>();
    });
    return g_httpClient.get();
}

} // namespace vdj
