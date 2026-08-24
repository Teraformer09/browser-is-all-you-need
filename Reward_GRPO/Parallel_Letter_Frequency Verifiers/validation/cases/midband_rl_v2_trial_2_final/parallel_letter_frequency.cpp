#include "parallel_letter_frequency.h"

#include <algorithm>
#include <cctype>
#include <numeric>

namespace parallel_letter_frequency {

std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts) {
    std::unordered_map<char, size_t> result;

    std::reduce(
        std::execution::par,
        texts.begin(), texts.end(),
        result,
        [](std::unordered_map<char, size_t>& accumulator,
           std::string_view const& text) {
            for (char const character : text) {
                if (std::isalpha(character)) {
                    accumulator[static_cast<char>(std::tolower(character))]++;
                }
            }
            return accumulator;
        });

    return result;
}

}  // namespace parallel_letter_frequency
