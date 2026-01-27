#include "http_client.h"
#include "vdjstem_writer.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <mutex>
#include <sstream>
#include <algorithm>
#include <cstring>

#pragma comment(lib, "winhttp.lib")

namespace vdj {

// Debug logging helper
static void DebugLog(const char* fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    OutputDebugStringA(buf);
}

namespace {
    constexpr DWORD CONNECT_TIMEOUT_MS = 10000;
    constexpr DWORD REQUEST_TIMEOUT_MS = 120000;  // 2 minutes for large payloads
    constexpr size_t MAX_PAYLOAD_SIZE = 50 * 1024 * 1024;  // 50MB limit

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

        try {
            return std::stoll(json.substr(pos));
        } catch (...) {
            return defaultVal;
        }
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

    std::string WideToUtf8(const std::wstring& str) {
        if (str.empty()) return "";
        int size = WideCharToMultiByte(CP_UTF8, 0, str.c_str(), (int)str.size(), nullptr, 0, nullptr, nullptr);
        std::string result(size, 0);
        WideCharToMultiByte(CP_UTF8, 0, str.c_str(), (int)str.size(), &result[0], size, nullptr, nullptr);
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
        DebugLog("HTTP: DoRequest START method=%S path=%S bodyLen=%zu\n",
                 method, path.c_str(), body.size());

        if (!hConnect) {
            DebugLog("HTTP: DoRequest FAIL - hConnect is null\n");
            return "";
        }

        // Check payload size limit
        if (body.size() > MAX_PAYLOAD_SIZE) {
            DebugLog("HTTP: DoRequest FAIL - payload too large (%zu > %zu bytes)\n",
                     body.size(), MAX_PAYLOAD_SIZE);
            return "";
        }

        // Validate body data is accessible
        if (!body.empty() && body.data() == nullptr) {
            DebugLog("HTTP: DoRequest FAIL - body data pointer is null\n");
            return "";
        }

        DWORD flags = useSSL ? WINHTTP_FLAG_SECURE : 0;
        DebugLog("HTTP: WinHttpOpenRequest flags=%u (SSL=%d)\n", flags, useSSL ? 1 : 0);

        HINTERNET hRequest = WinHttpOpenRequest(
            hConnect, method, path.c_str(), nullptr,
            WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags
        );
        if (!hRequest) {
            DWORD err = GetLastError();
            DebugLog("HTTP: WinHttpOpenRequest FAILED err=%u\n", err);
            return "";
        }
        DebugLog("HTTP: WinHttpOpenRequest OK hRequest=%p\n", hRequest);

        // Set timeouts
        WinHttpSetTimeouts(hRequest, REQUEST_TIMEOUT_MS, CONNECT_TIMEOUT_MS,
                          REQUEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS);

        // Set headers
        std::wstring headers;
        if (contentType) {
            headers = L"Content-Type: ";
            headers += contentType;
        }

        // Ignore SSL cert errors for testing
        DWORD secFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                        SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                        SECURITY_FLAG_IGNORE_CERT_CN_INVALID;
        if (!WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &secFlags, sizeof(secFlags))) {
            DWORD err = GetLastError();
            DebugLog("HTTP: WinHttpSetOption SECURITY_FLAGS warn err=%u\n", err);
        }

        DebugLog("HTTP: WinHttpSendRequest headers=%S bodyLen=%u\n",
                 headers.empty() ? L"(none)" : headers.c_str(), (DWORD)body.size());

        // For large payloads, log memory status
        if (body.size() > 10 * 1024 * 1024) {
            MEMORYSTATUSEX memStatus = {0};
            memStatus.dwLength = sizeof(memStatus);
            if (GlobalMemoryStatusEx(&memStatus)) {
                DebugLog("HTTP: Memory available: %llu MB (load: %u%%)\n",
                         memStatus.ullAvailPhys / (1024 * 1024), memStatus.dwMemoryLoad);
            }
        }

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
            DWORD err = GetLastError();
            DebugLog("HTTP: WinHttpSendRequest FAILED err=%u (0x%08X)\n", err, err);

            // Log specific error codes
            switch (err) {
                case ERROR_WINHTTP_CANNOT_CONNECT:
                    DebugLog("HTTP: ERROR_WINHTTP_CANNOT_CONNECT - server unavailable\n");
                    break;
                case ERROR_WINHTTP_TIMEOUT:
                    DebugLog("HTTP: ERROR_WINHTTP_TIMEOUT - request timed out\n");
                    break;
                case ERROR_WINHTTP_INVALID_SERVER_RESPONSE:
                    DebugLog("HTTP: ERROR_WINHTTP_INVALID_SERVER_RESPONSE\n");
                    break;
                case ERROR_NOT_ENOUGH_MEMORY:
                    DebugLog("HTTP: ERROR_NOT_ENOUGH_MEMORY - insufficient memory\n");
                    break;
                case ERROR_WINHTTP_OUT_OF_HANDLES:
                    DebugLog("HTTP: ERROR_WINHTTP_OUT_OF_HANDLES\n");
                    break;
                default:
                    DebugLog("HTTP: Unknown WinHTTP error\n");
            }

            WinHttpCloseHandle(hRequest);
            return "";
        }
        DebugLog("HTTP: WinHttpSendRequest OK\n");

        DebugLog("HTTP: WinHttpReceiveResponse...\n");
        if (!WinHttpReceiveResponse(hRequest, nullptr)) {
            DWORD err = GetLastError();
            DebugLog("HTTP: WinHttpReceiveResponse FAILED err=%u\n", err);
            WinHttpCloseHandle(hRequest);
            return "";
        }

        // Get status code
        DWORD statusCode = 0;
        DWORD statusSize = sizeof(statusCode);
        WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                           WINHTTP_HEADER_NAME_BY_INDEX, &statusCode, &statusSize, WINHTTP_NO_HEADER_INDEX);
        DebugLog("HTTP: Response status=%u\n", statusCode);

        // Read response
        std::string response;
        DWORD bytesRead = 0;
        char buffer[8192];

        while (WinHttpReadData(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
            response.append(buffer, bytesRead);
            DebugLog("HTTP: Read %u bytes (total %zu)\n", bytesRead, response.size());
        }

        WinHttpCloseHandle(hRequest);
        DebugLog("HTTP: DoRequest END responseLen=%zu\n", response.size());

        // Log first 500 chars of response for debugging
        if (!response.empty()) {
            std::string preview = response.substr(0, 500);
            DebugLog("HTTP: Response preview: %s\n", preview.c_str());
        }

        return response;
    }
};

HttpClient::HttpClient() : impl_(std::make_unique<Impl>()) {
    DebugLog("HTTP: HttpClient created\n");
}
HttpClient::~HttpClient() = default;

bool HttpClient::Connect(const std::string& base_url) {
    std::lock_guard<std::mutex> lock(impl_->mutex);

    DebugLog("HTTP: Connect START url=%s\n", base_url.c_str());

    // Parse URL
    std::string url = base_url;
    impl_->useSSL = true;
    impl_->port = INTERNET_DEFAULT_HTTPS_PORT;

    if (url.find("https://") == 0) {
        url = url.substr(8);
        DebugLog("HTTP: Parsed HTTPS, stripped prefix\n");
    } else if (url.find("http://") == 0) {
        url = url.substr(7);
        impl_->useSSL = false;
        impl_->port = INTERNET_DEFAULT_HTTP_PORT;
        DebugLog("HTTP: Parsed HTTP (no SSL)\n");
    }

    // Remove trailing slash
    while (!url.empty() && url.back() == '/') url.pop_back();

    // Check for port
    size_t colonPos = url.find(':');
    if (colonPos != std::string::npos) {
        impl_->port = (INTERNET_PORT)std::stoi(url.substr(colonPos + 1));
        url = url.substr(0, colonPos);
        DebugLog("HTTP: Custom port detected\n");
    }

    impl_->host = Utf8ToWide(url);
    DebugLog("HTTP: Host=%s Port=%u SSL=%d\n", url.c_str(), impl_->port, impl_->useSSL ? 1 : 0);

    // Create session
    DebugLog("HTTP: WinHttpOpen...\n");
    impl_->hSession = WinHttpOpen(
        L"VDJ-GPU-Proxy/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );
    if (!impl_->hSession) {
        DWORD err = GetLastError();
        DebugLog("HTTP: WinHttpOpen FAILED err=%u\n", err);
        return false;
    }
    DebugLog("HTTP: WinHttpOpen OK hSession=%p\n", impl_->hSession);

    // Set timeouts
    WinHttpSetTimeouts(impl_->hSession, CONNECT_TIMEOUT_MS, CONNECT_TIMEOUT_MS,
                      REQUEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS);

    // Connect
    DebugLog("HTTP: WinHttpConnect host=%S port=%u\n", impl_->host.c_str(), impl_->port);
    impl_->hConnect = WinHttpConnect(impl_->hSession, impl_->host.c_str(), impl_->port, 0);
    if (!impl_->hConnect) {
        DWORD err = GetLastError();
        DebugLog("HTTP: WinHttpConnect FAILED err=%u\n", err);
        WinHttpCloseHandle(impl_->hSession);
        impl_->hSession = nullptr;
        return false;
    }
    DebugLog("HTTP: WinHttpConnect OK hConnect=%p\n", impl_->hConnect);

    // Test connection with health check
    DebugLog("HTTP: Testing connection with /health...\n");
    std::string response = impl_->DoRequest(L"GET", L"/health", "", nullptr);
    impl_->connected = (response.find("\"status\"") != std::string::npos);

    if (!impl_->connected) {
        DebugLog("HTTP: Health check FAILED - response does not contain 'status'\n");
        DebugLog("HTTP: Full response: %s\n", response.c_str());
    } else {
        DebugLog("HTTP: Health check OK - connected!\n");
    }

    DebugLog("HTTP: Connect END connected=%d\n", impl_->connected ? 1 : 0);
    return impl_->connected;
}

void HttpClient::Disconnect() {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    DebugLog("HTTP: Disconnect\n");
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

    DebugLog("HTTP: GetServerInfo...\n");
    std::string response = impl_->DoRequest(L"GET", L"/info", "", nullptr);
    if (response.empty()) {
        DebugLog("HTTP: GetServerInfo - empty response\n");
        return info;
    }

    info.version = JsonGetString(response, "version");
    info.model_name = JsonGetString(response, "model_name");
    info.ready = JsonGetBool(response, "ready");
    info.max_batch_size = (int)JsonGetInt(response, "max_batch_size");

    DebugLog("HTTP: ServerInfo version=%s model=%s ready=%d\n",
             info.version.c_str(), info.model_name.c_str(), info.ready ? 1 : 0);
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

    DebugLog("HTTP: RunInference START session=%llu inputs=%zu outputs=%zu\n",
             session_id, input_names.size(), output_names.size());

    if (input_names.size() != inputs.size()) {
        result.error_message = "Input names count does not match inputs count";
        DebugLog("HTTP: RunInference FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Log input details
    for (size_t i = 0; i < inputs.size(); i++) {
        std::string shapeStr = "[";
        for (size_t j = 0; j < inputs[i].shape.size(); j++) {
            if (j > 0) shapeStr += ",";
            shapeStr += std::to_string(inputs[i].shape[j]);
        }
        shapeStr += "]";
        DebugLog("HTTP: Input[%zu] name=%s shape=%s dtype=%d dataLen=%zu\n",
                 i, input_names[i].c_str(), shapeStr.c_str(),
                 inputs[i].dtype, inputs[i].data.size());
    }

    std::lock_guard<std::mutex> lock(impl_->mutex);

    if (!impl_->connected || !impl_->hConnect) {
        result.error_message = "Not connected to server";
        DebugLog("HTTP: RunInference FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Build JSON request
    DebugLog("HTTP: Building JSON request...\n");

    // Calculate estimated size to check for potential OOM
    size_t estimatedSize = 1024;  // Base overhead
    for (const auto& inp : inputs) {
        estimatedSize += inp.data.size() * 4 / 3;  // Base64 overhead
        estimatedSize += 1024;  // JSON structure overhead
    }
    DebugLog("HTTP: Estimated JSON size: %zu bytes (%.2f MB)\n",
             estimatedSize, estimatedSize / (1024.0 * 1024.0));

    if (estimatedSize > MAX_PAYLOAD_SIZE) {
        result.error_message = "Payload would exceed size limit";
        DebugLog("HTTP: RunInference FAIL - %s (%zu > %zu)\n",
                 result.error_message.c_str(), estimatedSize, MAX_PAYLOAD_SIZE);
        return result;
    }

    // Build JSON with error handling
    std::string body;
    try {
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

            // Base64 encode - may throw on OOM
            std::string encoded = Base64Encode(inputs[i].data.data(), inputs[i].data.size());
            json << "\"data\":\"" << encoded << "\"}";
        }

        json << "],\"output_names\":[";
        for (size_t i = 0; i < output_names.size(); i++) {
            if (i > 0) json << ",";
            json << "\"" << JsonEscape(output_names[i]) << "\"";
        }
        json << "]}";

        body = json.str();
    }
    catch (const std::bad_alloc&) {
        result.error_message = "JSON building failed (out of memory)";
        DebugLog("HTTP: JSON building FAILED - out of memory\n");
        return result;
    }
    catch (const std::exception& e) {
        result.error_message = std::string("JSON building failed: ") + e.what();
        DebugLog("HTTP: JSON building FAILED - %s\n", e.what());
        return result;
    }
    catch (...) {
        result.error_message = "JSON building failed (unknown exception)";
        DebugLog("HTTP: JSON building FAILED - unknown exception\n");
        return result;
    }

    DebugLog("HTTP: Request JSON length=%zu\n", body.size());

    DebugLog("HTTP: Sending POST /inference...\n");
    std::string response = impl_->DoRequest(L"POST", L"/inference", body, L"application/json");

    if (response.empty()) {
        result.error_message = "Empty response from server";
        DebugLog("HTTP: RunInference FAIL - %s\n", result.error_message.c_str());
        return result;
    }
    DebugLog("HTTP: Got response length=%zu\n", response.size());

    // Check for error
    if (response.find("\"error\"") != std::string::npos ||
        response.find("\"detail\"") != std::string::npos) {
        result.error_message = JsonGetString(response, "error");
        if (result.error_message.empty()) {
            result.error_message = JsonGetString(response, "detail");
        }
        DebugLog("HTTP: Server returned error: %s\n", result.error_message.c_str());
        return result;
    }

    // Parse outputs array
    DebugLog("HTTP: Parsing outputs...\n");
    size_t outputsStart = response.find("\"outputs\"");
    if (outputsStart == std::string::npos) {
        result.error_message = "No outputs in response";
        DebugLog("HTTP: RunInference FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    size_t arrayStart = response.find('[', outputsStart);
    if (arrayStart == std::string::npos) {
        result.error_message = "Invalid outputs format";
        DebugLog("HTTP: RunInference FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Parse each output tensor
    size_t pos = arrayStart + 1;
    int outputIdx = 0;
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

        std::string shapeStr = "[";
        for (size_t j = 0; j < td.shape.size(); j++) {
            if (j > 0) shapeStr += ",";
            shapeStr += std::to_string(td.shape[j]);
        }
        shapeStr += "]";
        DebugLog("HTTP: Output[%d] shape=%s dtype=%d dataLen=%zu\n",
                 outputIdx, shapeStr.c_str(), td.dtype, td.data.size());

        result.outputs.push_back(std::move(td));
        outputIdx++;

        pos = objEnd + 1;
        // Skip to next { or break if ]
        while (pos < response.size() && response[pos] != '{' && response[pos] != ']') pos++;
        if (pos >= response.size() || response[pos] == ']') break;
    }

    DebugLog("HTTP: Parsed %zu outputs\n", result.outputs.size());
    result.success = true;
    DebugLog("HTTP: RunInference END success=true\n");
    return result;
}

// Binary protocol helpers
namespace BinaryProtocol {
    void WriteUint32(std::vector<uint8_t>& buf, uint32_t val) {
        buf.push_back(val & 0xFF);
        buf.push_back((val >> 8) & 0xFF);
        buf.push_back((val >> 16) & 0xFF);
        buf.push_back((val >> 24) & 0xFF);
    }

    void WriteInt64(std::vector<uint8_t>& buf, int64_t val) {
        for (int i = 0; i < 8; i++) {
            buf.push_back((val >> (i * 8)) & 0xFF);
        }
    }

    void WriteString(std::vector<uint8_t>& buf, const std::string& str) {
        WriteUint32(buf, (uint32_t)str.size());
        buf.insert(buf.end(), str.begin(), str.end());
    }

    void WriteShape(std::vector<uint8_t>& buf, const std::vector<int64_t>& shape) {
        WriteUint32(buf, (uint32_t)shape.size());
        for (int64_t dim : shape) {
            WriteInt64(buf, dim);
        }
    }

    void WriteTensor(std::vector<uint8_t>& buf, const std::string& name,
                     const std::vector<int64_t>& shape, uint32_t dtype,
                     const uint8_t* data, size_t dataLen) {
        WriteString(buf, name);
        WriteShape(buf, shape);
        WriteUint32(buf, dtype);
        WriteUint32(buf, (uint32_t)dataLen);
        buf.insert(buf.end(), data, data + dataLen);
    }

    uint32_t ReadUint32(const uint8_t* data, size_t& offset) {
        uint32_t val = data[offset] |
                       (data[offset + 1] << 8) |
                       (data[offset + 2] << 16) |
                       (data[offset + 3] << 24);
        offset += 4;
        return val;
    }

    int64_t ReadInt64(const uint8_t* data, size_t& offset) {
        int64_t val = 0;
        for (int i = 0; i < 8; i++) {
            val |= ((int64_t)data[offset + i]) << (i * 8);
        }
        offset += 8;
        return val;
    }

    std::string ReadString(const uint8_t* data, size_t& offset, size_t maxSize) {
        uint32_t len = ReadUint32(data, offset);
        if (offset + len > maxSize) {
            throw std::runtime_error("String read would exceed buffer");
        }
        std::string str((const char*)(data + offset), len);
        offset += len;
        return str;
    }

    std::vector<int64_t> ReadShape(const uint8_t* data, size_t& offset, size_t maxSize) {
        uint32_t ndim = ReadUint32(data, offset);
        if (ndim > 16) throw std::runtime_error("Invalid ndim");
        std::vector<int64_t> shape;
        for (uint32_t i = 0; i < ndim; i++) {
            if (offset + 8 > maxSize) {
                throw std::runtime_error("Shape read would exceed buffer");
            }
            shape.push_back(ReadInt64(data, offset));
        }
        return shape;
    }
}

HttpInferenceResult HttpClient::RunInferenceBinary(
    uint64_t session_id,
    const std::vector<std::string>& input_names,
    const std::vector<HttpTensorData>& inputs,
    const std::vector<std::string>& output_names
) {
    HttpInferenceResult result;
    result.success = false;

    DebugLog("HTTP: RunInferenceBinary START session=%llu inputs=%zu outputs=%zu\n",
             session_id, input_names.size(), output_names.size());

    if (input_names.size() != inputs.size()) {
        result.error_message = "Input names count does not match inputs count";
        DebugLog("HTTP: RunInferenceBinary FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    std::lock_guard<std::mutex> lock(impl_->mutex);

    if (!impl_->connected || !impl_->hConnect) {
        result.error_message = "Not connected to server";
        DebugLog("HTTP: RunInferenceBinary FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Build binary request
    DebugLog("HTTP: Building binary request...\n");
    std::vector<uint8_t> requestBuf;
    try {
        // Session ID
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)session_id);

        // Number of inputs
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)inputs.size());

        // Each input tensor
        for (size_t i = 0; i < inputs.size(); i++) {
            BinaryProtocol::WriteTensor(
                requestBuf,
                input_names[i],
                inputs[i].shape,
                inputs[i].dtype,
                inputs[i].data.data(),
                inputs[i].data.size()
            );

            std::string shapeStr = "[";
            for (size_t j = 0; j < inputs[i].shape.size(); j++) {
                if (j > 0) shapeStr += ",";
                shapeStr += std::to_string(inputs[i].shape[j]);
            }
            shapeStr += "]";
            DebugLog("HTTP: Binary Input[%zu] name=%s shape=%s dtype=%d dataLen=%zu\n",
                     i, input_names[i].c_str(), shapeStr.c_str(),
                     inputs[i].dtype, inputs[i].data.size());
        }

        // Number of outputs
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)output_names.size());

        // Each output name
        for (const auto& name : output_names) {
            BinaryProtocol::WriteString(requestBuf, name);
        }
    }
    catch (const std::exception& e) {
        result.error_message = std::string("Binary request building failed: ") + e.what();
        DebugLog("HTTP: Binary building FAILED - %s\n", e.what());
        return result;
    }

    DebugLog("HTTP: Binary request size=%zu bytes (%.2f MB)\n",
             requestBuf.size(), requestBuf.size() / (1024.0 * 1024.0));

    if (requestBuf.size() > MAX_PAYLOAD_SIZE) {
        result.error_message = "Binary payload exceeds size limit";
        DebugLog("HTTP: RunInferenceBinary FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Send binary request
    std::string requestBody((const char*)requestBuf.data(), requestBuf.size());
    DebugLog("HTTP: Sending POST /inference_binary...\n");
    std::string response = impl_->DoRequest(L"POST", L"/inference_binary", requestBody, L"application/octet-stream");

    if (response.empty()) {
        result.error_message = "Empty response from server";
        DebugLog("HTTP: RunInferenceBinary FAIL - %s\n", result.error_message.c_str());
        return result;
    }
    DebugLog("HTTP: Got binary response length=%zu\n", response.size());

    // Parse binary response
    try {
        const uint8_t* data = (const uint8_t*)response.data();
        size_t offset = 0;
        size_t maxSize = response.size();

        // Read session_id
        uint32_t respSessionId = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Binary response session_id=%u\n", respSessionId);

        // Read status
        uint32_t status = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Binary response status=%u\n", status);

        // Read error message
        std::string errorMsg = BinaryProtocol::ReadString(data, offset, maxSize);
        if (status != 0) {
            result.error_message = errorMsg.empty() ? "Server returned error" : errorMsg;
            DebugLog("HTTP: Server error: %s\n", result.error_message.c_str());
            return result;
        }

        // Read number of outputs
        uint32_t numOutputs = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Binary response num_outputs=%u\n", numOutputs);

        // Parse each output tensor
        for (uint32_t i = 0; i < numOutputs; i++) {
            std::string outputName = BinaryProtocol::ReadString(data, offset, maxSize);
            std::vector<int64_t> shape = BinaryProtocol::ReadShape(data, offset, maxSize);
            uint32_t dtype = BinaryProtocol::ReadUint32(data, offset);
            uint32_t dataLen = BinaryProtocol::ReadUint32(data, offset);

            if (offset + dataLen > maxSize) {
                throw std::runtime_error("Tensor data would exceed buffer");
            }

            HttpTensorData td;
            td.shape = shape;
            td.dtype = dtype;
            td.data.assign(data + offset, data + offset + dataLen);
            offset += dataLen;

            std::string shapeStr = "[";
            for (size_t j = 0; j < shape.size(); j++) {
                if (j > 0) shapeStr += ",";
                shapeStr += std::to_string(shape[j]);
            }
            shapeStr += "]";
            DebugLog("HTTP: Binary Output[%u] name=%s shape=%s dtype=%d dataLen=%u\n",
                     i, outputName.c_str(), shapeStr.c_str(), dtype, dataLen);

            result.outputs.push_back(std::move(td));
        }

        DebugLog("HTTP: Parsed %zu binary outputs\n", result.outputs.size());
        result.success = true;
        DebugLog("HTTP: RunInferenceBinary END success=true\n");
    }
    catch (const std::exception& e) {
        result.error_message = std::string("Binary response parsing failed: ") + e.what();
        DebugLog("HTTP: Binary parsing FAILED - %s\n", e.what());
        return result;
    }

    return result;
}

VdjStemResult HttpClient::CreateVdjStem(
    uint64_t session_id,
    const HttpTensorData& audio_input,
    const std::string& stems_folder
) {
    VdjStemResult result;
    result.success = false;
    result.cache_hit = false;

    DebugLog("HTTP: CreateVdjStem START session=%llu stemsFolder=%s\n",
             session_id, stems_folder.c_str());

    std::lock_guard<std::mutex> lock(impl_->mutex);

    if (!impl_->connected || !impl_->hConnect) {
        result.error_message = "Not connected to server";
        DebugLog("HTTP: CreateVdjStem FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    // Build binary request
    std::vector<uint8_t> requestBuf;
    try {
        // Session ID
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)session_id);

        // Audio shape
        BinaryProtocol::WriteShape(requestBuf, audio_input.shape);

        // dtype
        BinaryProtocol::WriteUint32(requestBuf, audio_input.dtype);

        // data length and data
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)audio_input.data.size());
        requestBuf.insert(requestBuf.end(), audio_input.data.begin(), audio_input.data.end());

        // Request all 4 stems
        const std::vector<std::string> stem_names = {"drums", "bass", "other", "vocals"};
        BinaryProtocol::WriteUint32(requestBuf, (uint32_t)stem_names.size());
        for (const auto& name : stem_names) {
            BinaryProtocol::WriteString(requestBuf, name);
        }

    } catch (const std::exception& e) {
        result.error_message = std::string("Request building failed: ") + e.what();
        DebugLog("HTTP: CreateVdjStem request build FAILED - %s\n", e.what());
        return result;
    }

    DebugLog("HTTP: CreateVdjStem request size=%zu bytes (%.2f MB)\n",
             requestBuf.size(), requestBuf.size() / (1024.0 * 1024.0));

    // Send request using existing DoRequest
    std::string requestBody((const char*)requestBuf.data(), requestBuf.size());
    std::string response = impl_->DoRequest(L"POST", L"/create_vdjstem", requestBody, L"application/octet-stream");

    if (response.empty()) {
        result.error_message = "Empty response from server";
        DebugLog("HTTP: CreateVdjStem FAIL - %s\n", result.error_message.c_str());
        return result;
    }

    DebugLog("HTTP: Received response: %zu bytes\n", response.size());

    // Parse binary response
    try {
        const uint8_t* data = (const uint8_t*)response.data();
        size_t offset = 0;
        size_t maxSize = response.size();

        // Read session_id
        uint32_t respSessionId = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Response session_id=%u\n", respSessionId);

        // Read status
        uint32_t status = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Response status=%u\n", status);

        // Read error message
        std::string errorMsg = BinaryProtocol::ReadString(data, offset, maxSize);
        if (status != 0) {
            result.error_message = errorMsg.empty() ? "Server returned error" : errorMsg;
            DebugLog("HTTP: Server error: %s\n", result.error_message.c_str());
            return result;
        }

        // Read audio hash
        result.audio_hash = BinaryProtocol::ReadString(data, offset, maxSize);
        DebugLog("HTTP: Audio hash: %s\n", result.audio_hash.c_str());

        // Read stem file content
        uint32_t stemFileLen = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Stem file length: %u bytes\n", stemFileLen);

        std::vector<uint8_t> stemFileContent;
        if (stemFileLen > 0) {
            if (offset + stemFileLen > maxSize) {
                throw std::runtime_error("Stem file would exceed buffer");
            }
            stemFileContent.assign(data + offset, data + offset + stemFileLen);
            offset += stemFileLen;
            result.cache_hit = false;  // File was created

            // Save the file locally
            std::string subdir = result.audio_hash.substr(0, 2);
            std::string stemDir = stems_folder + "\\" + subdir;

            CreateDirectoryA(stems_folder.c_str(), NULL);
            CreateDirectoryA(stemDir.c_str(), NULL);

            result.local_path = stemDir + "\\" + result.audio_hash + ".vdjstem";

            HANDLE hFile = CreateFileA(
                result.local_path.c_str(),
                GENERIC_WRITE,
                0,
                NULL,
                CREATE_ALWAYS,
                FILE_ATTRIBUTE_NORMAL,
                NULL
            );

            if (hFile != INVALID_HANDLE_VALUE) {
                DWORD bytesWritten = 0;
                WriteFile(hFile, stemFileContent.data(), (DWORD)stemFileContent.size(), &bytesWritten, NULL);
                CloseHandle(hFile);
                DebugLog("HTTP: VDJStem saved to: %s (%u bytes)\n", result.local_path.c_str(), bytesWritten);
            } else {
                DWORD err = GetLastError();
                DebugLog("HTTP: Warning - failed to save VDJStem file (err=%u)\n", err);
            }
        }

        // Read number of output tensors
        uint32_t numOutputs = BinaryProtocol::ReadUint32(data, offset);
        DebugLog("HTTP: Number of output tensors: %u\n", numOutputs);

        // Parse each output tensor
        for (uint32_t i = 0; i < numOutputs; i++) {
            std::string outputName = BinaryProtocol::ReadString(data, offset, maxSize);
            std::vector<int64_t> shape = BinaryProtocol::ReadShape(data, offset, maxSize);
            uint32_t dtype = BinaryProtocol::ReadUint32(data, offset);
            uint32_t dataLen = BinaryProtocol::ReadUint32(data, offset);

            if (offset + dataLen > maxSize) {
                throw std::runtime_error("Tensor data would exceed buffer");
            }

            HttpTensorData td;
            td.shape = shape;
            td.dtype = dtype;
            td.data.assign(data + offset, data + offset + dataLen);
            offset += dataLen;

            std::string shapeStr = "[";
            for (size_t j = 0; j < shape.size(); j++) {
                if (j > 0) shapeStr += ",";
                shapeStr += std::to_string(shape[j]);
            }
            shapeStr += "]";
            DebugLog("HTTP: Output[%u] name=%s shape=%s dtype=%d dataLen=%u\n",
                     i, outputName.c_str(), shapeStr.c_str(), dtype, dataLen);

            result.outputs.push_back(std::move(td));
        }

        DebugLog("HTTP: Parsed %zu output tensors\n", result.outputs.size());

        // If server didn't create the VDJStem file, create it client-side
        if (stemFileLen == 0 && result.outputs.size() == 4) {
            DebugLog("HTTP: Creating VDJStem file client-side...\n");

            // Build stem data for writer
            std::vector<std::pair<std::string, std::vector<float>>> stem_data;
            const char* stem_names[] = {"drums", "bass", "other", "vocals"};

            for (size_t i = 0; i < 4; i++) {
                const auto& tensor = result.outputs[i];
                // Convert uint8_t data to float
                size_t num_floats = tensor.data.size() / sizeof(float);
                std::vector<float> floats(num_floats);
                memcpy(floats.data(), tensor.data.data(), tensor.data.size());
                stem_data.push_back({stem_names[i], std::move(floats)});
            }

            // Create output path
            std::string subdir = result.audio_hash.substr(0, 2);
            std::string stemDir = stems_folder + "\\" + subdir;
            CreateDirectoryA(stems_folder.c_str(), NULL);
            CreateDirectoryA(stemDir.c_str(), NULL);
            result.local_path = stemDir + "\\" + result.audio_hash + ".vdjstem";

            // Create the file
            if (CreateVdjStemFile(stem_data, result.local_path, 44100)) {
                DebugLog("HTTP: VDJStem file created: %s\n", result.local_path.c_str());
            } else {
                DebugLog("HTTP: Warning - failed to create VDJStem file (ffmpeg missing?)\n");
                // Not a fatal error - we still have the tensors
            }
        }

        result.success = true;

    } catch (const std::exception& e) {
        result.error_message = std::string("Response parsing failed: ") + e.what();
        DebugLog("HTTP: Response parsing FAILED - %s\n", e.what());
        return result;
    }

    return result;
}

// Helper to compute audio hash on client side (for cache checking)
std::string ComputeAudioHash(const float* audio_data, size_t num_samples) {
    // Use first 10 seconds at 44100Hz
    size_t max_samples = 44100 * 10 * 2;  // 10 sec stereo
    size_t samples_to_hash = (num_samples < max_samples) ? num_samples : max_samples;

    // Simple hash using polynomial rolling hash
    uint64_t hash = 0;
    const uint64_t prime = 31;
    for (size_t i = 0; i < samples_to_hash; i++) {
        int16_t sample = (int16_t)(audio_data[i] * 32767);
        hash = hash * prime + (uint64_t)(uint16_t)sample;
    }

    // Convert to hex string
    char hex[17];
    snprintf(hex, sizeof(hex), "%016llx", hash);
    return std::string(hex);
}

static std::unique_ptr<HttpClient> g_httpClient;
static std::once_flag g_httpClientInit;

HttpClient* GetHttpClient() {
    std::call_once(g_httpClientInit, []() {
        g_httpClient = std::make_unique<HttpClient>();
        DebugLog("HTTP: Global HttpClient initialized\n");
    });
    return g_httpClient.get();
}

} // namespace vdj
