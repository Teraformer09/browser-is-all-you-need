# Instructions

Count the frequency of letters in texts using parallel computation.

Parallelism is about doing things in parallel that can also be done sequentially.
A common example is counting the frequency of letters.
Employ parallelism to calculate the total frequency of each letter in a list of texts.


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace parallel_letter_frequency {
std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts);
}
```

Count ASCII letters case-insensitively, keyed by the lowercase letter. Non-letters are ignored. Despite the exercise name, a correct single-threaded implementation passes the tests.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `parallel_letter_frequency.h` and `parallel_letter_frequency.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `parallel_letter_frequency.h`, so every name above must be visible
  from that header.
- You may either declare in `parallel_letter_frequency.h` and define in `parallel_letter_frequency.cpp`, or define
  everything `inline`/in-class in `parallel_letter_frequency.h` and leave `parallel_letter_frequency.cpp` unchanged.
  Both are accepted.
