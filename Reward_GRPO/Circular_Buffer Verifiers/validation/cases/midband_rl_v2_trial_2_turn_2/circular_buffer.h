#pragma once

#include <cstddef>
#include <stdexcept>
#include <vector>

namespace circular_buffer {

template <typename ValueType>
class circular_buffer {
public:
    circular_buffer(std::size_t capacity);
    ValueType read();
    void write(ValueType item);
    void overwrite(ValueType item);
    void clear();

private:
    std::vector<ValueType> buffer_;
    std::size_t capacity_;
    std::size_t head_;
    std::size_t tail_;
    std::size_t count_;
};

template <typename ValueType>
circular_buffer<ValueType>::circular_buffer(std::size_t capacity)
    : capacity_(capacity), head_(0), tail_(0), count_(0) {
    buffer_.resize(capacity_);
}

template <typename ValueType>
ValueType circular_buffer<ValueType>::read() {
    if (count_ == 0) {
        throw std::domain_error("buffer is empty");
    }
    ValueType item = buffer_[head_];
    head_ = (head_ + 1) % capacity_;
    --count_;
    return item;
}

template <typename ValueType>
void circular_buffer<ValueType>::write(ValueType item) {
    if (count_ == capacity_) {
        throw std::domain_error("buffer is full");
    }
    buffer_[tail_] = item;
    tail_ = (tail_ + 1) % capacity_;
    ++count_;
}

template <typename ValueType>
void circular_buffer<ValueType>::overwrite(ValueType item) {
    if (count_ == capacity_) {
        buffer_[head_] = item;
        head_ = (head_ + 1) % capacity_;
    } else {
        write(item);
    }
}

template <typename ValueType>
void circular_buffer<ValueType>::clear() {
    head_ = 0;
    tail_ = 0;
    count_ = 0;
}

}  // namespace circular_buffer
