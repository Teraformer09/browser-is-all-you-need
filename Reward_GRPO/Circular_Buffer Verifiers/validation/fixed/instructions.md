# Instructions

A circular buffer, cyclic buffer or ring buffer is a data structure that uses a single, fixed-size buffer as if it were connected end-to-end.

A circular buffer first starts empty and of some predefined length.
For example, this is a 7-element buffer:

```text
[ ][ ][ ][ ][ ][ ][ ]
```

Assume that a 1 is written into the middle of the buffer (exact starting location does not matter in a circular buffer):

```text
[ ][ ][ ][1][ ][ ][ ]
```

Then assume that two more elements are added — 2 & 3 — which get appended after the 1:

```text
[ ][ ][ ][1][2][3][ ]
```

If two elements are then removed from the buffer, the oldest values inside the buffer are removed.
The two elements removed, in this case, are 1 & 2, leaving the buffer with just a 3:

```text
[ ][ ][ ][ ][ ][3][ ]
```

If the buffer has 7 elements then it is completely full:

```text
[5][6][7][8][9][3][4]
```

When the buffer is full an error will be raised, alerting the client that further writes are blocked until a slot becomes free.

When the buffer is full, the client can opt to overwrite the oldest data with a forced write.
In this case, two more elements — A & B — are added and they overwrite the 3 & 4:

```text
[5][6][7][8][9][A][B]
```

3 & 4 have been replaced by A & B making 5 now the oldest data in the buffer.
Finally, if two elements are removed then what would be returned is 5 & 6 yielding the buffer:

```text
[ ][ ][7][8][9][A][B]
```

Because there is space available, if the client again uses overwrite to store C & D then the space where 5 & 6 were stored previously will be used not the location of 7 & 8.
7 is still the oldest element and the buffer is once again full.

```text
[C][D][7][8][9][A][B]
```


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace circular_buffer {
template <typename ValueType>
class circular_buffer {
public:
    circular_buffer(std::size_t capacity);
    ValueType read();
    void write(ValueType item);
    void overwrite(ValueType item);
    void clear();
};
}
```

`read()` on an empty buffer and `write()` on a full buffer both throw `std::domain_error`. `overwrite()` on a full buffer replaces the oldest element instead of throwing. The tests instantiate the template with both `int` and `std::string`.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `circular_buffer.h` and `circular_buffer.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `circular_buffer.h`, so every name above must be visible
  from that header.
- The declarations above are templates, so their definitions must live in
  `circular_buffer.h`. Leaving `circular_buffer.cpp` unchanged is fine.
