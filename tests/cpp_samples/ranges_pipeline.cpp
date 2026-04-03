#include <array>
#include <concepts>
#include <ranges>

template <typename T>
struct RangeBox {
    T value;
};

template <typename Range>
concept ArithmeticRange = std::ranges::input_range<Range>
    && std::integral<std::ranges::range_value_t<Range>>;

template <ArithmeticRange Range>
struct RangeProjection {
    static auto build(Range&& values) {
        return values
            | std::views::filter([](auto value) { return value % 2 == 0; })
            | std::views::transform([](auto value) { return RangeBox<decltype(value)>{value * 3}; })
            | std::views::transform([](auto boxed) { return boxed.value + 1; });
    }
};

template <ArithmeticRange Range>
int consume_range(Range&& values) {
    int total = 0;
    for (auto value : RangeProjection<Range>::build(std::forward<Range>(values))) {
        total += value;
    }
    return total;
}

int run_ranges_pipeline() {
    std::array<int, 16> values{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
    return consume_range(values);
}
