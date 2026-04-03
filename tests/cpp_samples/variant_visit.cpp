#include <string>
#include <utility>
#include <variant>

template <typename T>
struct VariantPayload {
    T value;
};

template <typename... Ts>
using DemoVariant = std::variant<VariantPayload<Ts>...>;

template <typename... Callables>
struct Overloaded : Callables... {
    using Callables::operator()...;
};
template <typename... Callables>
Overloaded(Callables...) -> Overloaded<Callables...>;

template <typename Variant>
struct VariantDispatcher;

template <typename... Ts>
struct VariantDispatcher<DemoVariant<Ts...>> {
    static auto run(const DemoVariant<Ts...>& value) {
        return std::visit(
            Overloaded{
                [](const VariantPayload<int>& payload) { return payload.value + 1; },
                [](const VariantPayload<long>& payload) { return static_cast<int>(payload.value + 2); },
                [](const VariantPayload<double>& payload) { return static_cast<int>(payload.value + 3.0); },
                [](const VariantPayload<char>& payload) { return static_cast<int>(payload.value); },
                [](const VariantPayload<bool>& payload) { return payload.value ? 7 : 0; },
                [](const VariantPayload<short>& payload) { return payload.value + 5; },
                [](const VariantPayload<std::string>& payload) {
                    return static_cast<int>(payload.value.size());
                },
            },
            value
        );
    }
};

using SampleVariant = DemoVariant<int, long, double, char, bool, short, std::string>;

int run_variant_dispatch() {
    return VariantDispatcher<SampleVariant>::run(VariantPayload<int>{42});
}
