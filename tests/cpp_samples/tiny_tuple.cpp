#include <tuple>

template <typename T>
struct TinyWrap {
    using type = T;
};

template <typename... Ts>
using TinyTuple = std::tuple<typename TinyWrap<Ts>::type...>;

TinyTuple<int, double, char, long> tiny_value;
