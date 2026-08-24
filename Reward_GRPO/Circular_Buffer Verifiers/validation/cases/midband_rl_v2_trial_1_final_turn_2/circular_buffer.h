#pragma once

#include <cstddef>
#include <stdexcept>
#include <utility>
#include <vector>

namespace circular_buffer {

template <typename ValueType>
class circular_buffer {
public:
    explicit circular_buffer(std::size_t capacity)
        : capacity_(capacity), storage_(capacity), head_(0), tail_(0), size_(0) {}

    ValueType read() {
        if (capacity_ == 0) {
            throw std::domain_error("invalid capacity");
        }
        if (head_ == tail_) {
            throw std::domain_error("buffer is empty");
        }
        ValueType value = std::move(storage_[head_]);
        head_ = (head_ + 1) % capacity_;
        --size_;
        return value;
    }

    void write(ValueType item) {
        if (capacity_ == 0) {
            throw std::domain_error("invalid capacity");
        }
        if (head_ == tail_) {
            throw std::domain_error("buffer is full");
        }
        storage_[tail_] = std::move(item);
        tail_ = (tail_ + 1) % capacity_;
        ++size_;
    }

    void overwrite(ValueType item) {
        if (capacity_ == 0) {
            throw std::domain_error("invalid capacity");
        }
        if (head_ == tail_) {
            storage_[head_] = std::move(item);
            head_ = (head_ + 1) % capacity_;
        } else {
            storage_[tail_] = std::move(item);
            tail_ = (tail_ + 1) % capacity_;
        }
        ++size_;
    }

    void clear() {
        head_ = 0;
        tail_ = 0;
        size_ = 0;
    }

private:
    std::size_t capacity_;
    std::vector<ValueType> storage_;
    std::size_t head_;
    std::size_t tail_;
    std::size_t size_;
};

}  // namespace circular_buffer
