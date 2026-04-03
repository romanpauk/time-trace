#include <cstddef>
#include <type_traits>

template <int... Values>
struct ValueList {};

template <typename List, int Value>
struct AppendValue;

template <int... Values, int Value>
struct AppendValue<ValueList<Values...>, Value> {
    using type = ValueList<Values..., Value>;
};

template <std::size_t Count>
struct MakeSequence {
    using type = typename AppendValue<typename MakeSequence<Count - 1>::type, static_cast<int>(Count - 1)>::type;
};

template <>
struct MakeSequence<0> {
    using type = ValueList<>;
};

template <typename List>
struct IncrementAll;

template <int... Values>
struct IncrementAll<ValueList<Values...>> {
    using type = ValueList<(Values + 1)...>;
};

template <typename Left, typename Right>
struct Concat;

template <int... Left, int... Right>
struct Concat<ValueList<Left...>, ValueList<Right...>> {
    using type = ValueList<Left..., Right...>;
};

template <std::size_t Index, typename List>
struct ValueAt;

template <std::size_t Index, int Head, int... Tail>
struct ValueAt<Index, ValueList<Head, Tail...>> : ValueAt<Index - 1, ValueList<Tail...>> {};

template <int Head, int... Tail>
struct ValueAt<0, ValueList<Head, Tail...>> {
    static constexpr int value = Head;
};

using Base = typename MakeSequence<96>::type;
using Incremented = typename IncrementAll<Base>::type;
using Combined = typename Concat<Base, Incremented>::type;

static_assert(ValueAt<100, Combined>::value == 5);
Combined values{};
