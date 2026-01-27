#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <iostream>
#include <vector>
#include <string>
#include <memory>
#include <mutex>
#include <sstream>
#include <cstdarg>

#pragma comment(lib, "winhttp.lib")

// Redirect OutputDebugString to stdout for testing
#define OutputDebugStringA(x) std::cout << x

namespace vdj {

// Debug logging helper
static void DebugLog(const char* fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    std::cout << buf << std::flush;
}

// Copy the entire http_client implementation here...
// [Include all the code from http_client.cpp]

namespace {
    constexpr DWORD CONNECT_TIMEOUT_MS = 10000;
    constexpr DWORD REQUEST_TIMEOUT_MS = 60000;

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

    std::wstring Utf8ToWide(const std::string& str) {
        if (str.empty()) return L"";
        int size = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), nullptr, 0);
        std::wstring result(size, 0);
        MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), &result[0], size);
        return result;
    }
}

struct HttpTensorData {
    std::vector<int64_t> shape;
    int32_t dtype;
    std::vector<uint8_t> data;
};

struct HttpInferenceResult {
    bool success;
    std::string error_message;
    std::vector<HttpTensorData> outputs;
};

struct ServerInfo {
    std::string version;
    std::string model_name;
    bool ready;
    int max_batch_size;
};

class HttpClient {
public:
    bool Connect(const std::string& url) {
        DebugLog("TEST: Connect START url=%s\n", url.c_str());

        std::string host = url;
        bool useSSL = true;
        INTERNET_PORT port = INTERNET_DEFAULT_HTTPS_PORT;

        if (host.find("https://") == 0) {
            host = host.substr(8);
        }

        while (!host.empty() && host.back() == '/') host.pop_back();

        std::wstring whost = Utf8ToWide(host);
        DebugLog("TEST: Host=%s Port=%u SSL=%d\n", host.c_str(), port, useSSL ? 1 : 0);

        hSession = WinHttpOpen(L"VDJ-Test/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                              WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
        if (!hSession) {
            DWORD err = GetLastError();
            DebugLog("TEST: WinHttpOpen FAILED err=%u\n", err);
            return false;
        }
        DebugLog("TEST: WinHttpOpen OK\n");

        hConnect = WinHttpConnect(hSession, whost.c_str(), port, 0);
        if (!hConnect) {
            DWORD err = GetLastError();
            DebugLog("TEST: WinHttpConnect FAILED err=%u\n", err);
            return false;
        }
        DebugLog("TEST: WinHttpConnect OK\n");

        // Test /health
        HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", L"/health", nullptr,
                                               WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
                                               WINHTTP_FLAG_SECURE);
        if (!hRequest) {
            DebugLog("TEST: WinHttpOpenRequest FAILED err=%u\n", GetLastError());
            return false;
        }

        DWORD secFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                        SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                        SECURITY_FLAG_IGNORE_CERT_CN_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &secFlags, sizeof(secFlags));

        if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                               WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
            DebugLog("TEST: WinHttpSendRequest FAILED err=%u\n", GetLastError());
            WinHttpCloseHandle(hRequest);
            return false;
        }

        if (!WinHttpReceiveResponse(hRequest, nullptr)) {
            DebugLog("TEST: WinHttpReceiveResponse FAILED err=%u\n", GetLastError());
            WinHttpCloseHandle(hRequest);
            return false;
        }

        DWORD statusCode = 0;
        DWORD statusSize = sizeof(statusCode);
        WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                           WINHTTP_HEADER_NAME_BY_INDEX, &statusCode, &statusSize,
                           WINHTTP_NO_HEADER_INDEX);
        DebugLog("TEST: Response status=%u\n", statusCode);

        char buffer[1024];
        DWORD bytesRead;
        std::string response;
        while (WinHttpReadData(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
            response.append(buffer, bytesRead);
        }

        WinHttpCloseHandle(hRequest);
        DebugLog("TEST: Response: %s\n", response.c_str());

        connected = (response.find("\"status\"") != std::string::npos);
        DebugLog("TEST: Connected=%d\n", connected ? 1 : 0);
        return connected;
    }

    ~HttpClient() {
        if (hConnect) WinHttpCloseHandle(hConnect);
        if (hSession) WinHttpCloseHandle(hSession);
    }

private:
    HINTERNET hSession = nullptr;
    HINTERNET hConnect = nullptr;
    bool connected = false;
};

} // namespace vdj

int main() {
    std::cout << "=== HTTP Client Standalone Test ===" << std::endl;

    vdj::HttpClient client;

    std::string url = "https://vdj-gpu-direct.ai-smith.net";
    std::cout << "\nTesting: " << url << std::endl;

    bool result = client.Connect(url);

    std::cout << "\n=== Result: " << (result ? "SUCCESS" : "FAILED") << " ===" << std::endl;

    return result ? 0 : 1;
}
