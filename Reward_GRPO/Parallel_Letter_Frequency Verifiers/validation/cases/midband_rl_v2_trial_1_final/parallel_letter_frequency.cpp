#include "parallel_letter_frequency.h"

#include <array>
#include <execution>
#include <utility>

namespace parallel_letter_frequency {

std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts) {
    std::array<size_t, 26> counts{};
    std::for_each(std::execution::par, texts.begin(), texts.end(),
        [&counts](std::string_view text) {
            for (const char character : text) {
                const auto lower = static_cast<char>(std::tolower(character));
                if (std::isalnum(lower) && lower >= 'a' && lower <= 'z') {
                    ++counts[static_cast<std::size_t>(lower - 'a')];
                }
            }
        });
    std::unordered_map<char, size_t> result;
    for (std::size_t index = 0; index < counts.size(); ++index) {
        const char letter = static_cast<char>('a' + index);
        if (counts[index] > 0) {
            result[letter] = counts[index];
        }
    }
    return result;
}

}  // namespace parallel_letter_frequency
