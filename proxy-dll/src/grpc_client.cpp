#include "grpc_client.h"
#include <grpcpp/grpcpp.h>
#include "stems.grpc.pb.h"
#include <mutex>
#include <chrono>

namespace vdj {

namespace {
    constexpr size_t MAX_MESSAGE_SIZE = 100 * 1024 * 1024;  // 100MB
    constexpr int CONNECT_TIMEOUT_SECONDS = 5;
    constexpr int INFERENCE_TIMEOUT_SECONDS = 30;
}

class GrpcClient::Impl {
public:
    std::unique_ptr<stems::StemsInference::Stub> stub;
    std::shared_ptr<grpc::Channel> channel;
    mutable std::mutex mutex;
    bool connected = false;
};

GrpcClient::GrpcClient() : impl_(std::make_unique<Impl>()) {}
GrpcClient::~GrpcClient() = default;

bool GrpcClient::Connect(const std::string& address, uint16_t port) {
    std::lock_guard<std::mutex> lock(impl_->mutex);

    std::string target = address + ":" + std::to_string(port);

    grpc::ChannelArguments args;
    args.SetMaxReceiveMessageSize(MAX_MESSAGE_SIZE); // 100MB for large tensors
    args.SetMaxSendMessageSize(MAX_MESSAGE_SIZE);

    impl_->channel = grpc::CreateCustomChannel(
        target,
        grpc::InsecureChannelCredentials(),
        args
    );

    impl_->stub = stems::StemsInference::NewStub(impl_->channel);

    // Test connection
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(CONNECT_TIMEOUT_SECONDS));

    stems::Empty request;
    stems::ServerInfo response;

    grpc::Status status = impl_->stub->GetServerInfo(&context, request, &response);

    impl_->connected = status.ok() && response.ready();
    return impl_->connected;
}

void GrpcClient::Disconnect() {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    impl_->stub.reset();
    impl_->channel.reset();
    impl_->connected = false;
}

bool GrpcClient::IsConnected() const {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    return impl_->connected;
}

InferenceResult GrpcClient::RunInference(
    uint64_t session_id,
    const std::vector<std::string>& input_names,
    const std::vector<TensorData>& inputs,
    const std::vector<std::string>& output_names
) {
    InferenceResult result;
    result.success = false;

    if (input_names.size() != inputs.size()) {
        result.error_message = "Input names count does not match inputs count";
        return result;
    }

    std::lock_guard<std::mutex> lock(impl_->mutex);

    if (!impl_->connected || !impl_->stub) {
        result.error_message = "Not connected to server";
        return result;
    }

    // Build request
    stems::InferenceRequest request;
    request.set_session_id(session_id);

    for (const auto& name : input_names) {
        request.add_input_names(name);
    }

    for (const auto& tensor : inputs) {
        auto* t = request.add_inputs();
        for (int64_t dim : tensor.shape) {
            t->mutable_shape()->add_dims(dim);
        }
        t->set_dtype(tensor.dtype);
        t->set_data(tensor.data.data(), tensor.data.size());
    }

    for (const auto& name : output_names) {
        request.add_output_names(name);
    }

    // Call server
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(INFERENCE_TIMEOUT_SECONDS));

    stems::InferenceResponse response;
    grpc::Status status = impl_->stub->RunInference(&context, request, &response);

    if (!status.ok()) {
        result.error_message = "gRPC error: " + status.error_message();
        return result;
    }

    if (response.status() != 0) {
        result.error_message = response.error_message();
        return result;
    }

    // Extract outputs
    for (const auto& tensor : response.outputs()) {
        TensorData td;
        for (int i = 0; i < tensor.shape().dims_size(); i++) {
            td.shape.push_back(tensor.shape().dims(i));
        }
        td.dtype = tensor.dtype();
        const std::string& data = tensor.data();
        td.data.assign(data.begin(), data.end());
        result.outputs.push_back(std::move(td));
    }

    result.success = true;
    return result;
}

// Global instance
static std::unique_ptr<GrpcClient> g_client;
static std::once_flag g_client_init;

GrpcClient* GetGrpcClient() {
    std::call_once(g_client_init, []() {
        g_client = std::make_unique<GrpcClient>();
    });
    return g_client.get();
}

} // namespace vdj
