#include "parallel_letter_frequency.h"

#include <vector>

namespace parallel_letter_frequency {

std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts) {
    if (texts.empty()) {
        return {};
    }

    // Helper lambda to count letters in a single string
    auto count_range = [](std::string_view text) {
        std::unordered_map<char, size_t> counts;
        for (const char raw : text) {
            const char letter = static_cast<char>(std::tolower(raw));
            if (std::isalpha(letter)) {
                ++counts[letter];
            }
        }
        return counts;
    };

    // Step 1: Count in parallel and store partial results
    std::vector<std::unordered_map<char, size_t>> partial_counts(
        texts.size());
    std::transform(
        std::execution::par,
        texts.begin(), texts.end(),
        partial_counts.begin(),
        count_range);

    // Step 2: Merge partial results into the final map
    std::unordered_map<char, size_t> result;
    for (const auto& partial : partial_counts) {
        for (const auto& [letter, count] : partial) {
            result[letter] += count;
        }
    }

    return result;
}

}  // namespace parallel_letter_frequency
