#include "parallel_letter_frequency.h"

#include <algorithm>
#include <thread>
#include <utility>
#include <vector>

namespace parallel_letter_frequency {

std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts) {
    if (texts.empty()) {
        return {};
    }

    std::unordered_map<char, size_t> result;
    std::vector<std::thread> threads;
    const auto num_threads = std::max(
        1U, std::thread::hardware_concurrency());
    const auto chunk_size = (texts.size() + num_threads - 1) / num_threads;

    for (unsigned int t = 0; t < num_threads; ++t) {
        const auto begin = texts.begin() + t * chunk_size;
        const auto end = std::min(
            texts.begin() + t * chunk_size + chunk_size, texts.end());
        threads.emplace_back([begin, end, &result]() {
            std::unordered_map<char, size_t> local_result;
            for (auto const& text : std::vector<std::string_view>(begin, end)) {
                for (auto const character : text) {
                    const auto byte = static_cast<unsigned char>(character);
                    if (std::isalnum(byte) != 0) {
                        local_result[std::tolower(byte)]++;
                    }
                }
            }
            for (auto const& [letter, count] : local_result) {
                result[letter] += count;
            }
        });
    }

    for (auto& thread : threads) {
        thread.join();
    }
    return result;
}

}  // namespace parallel_letter_frequency
