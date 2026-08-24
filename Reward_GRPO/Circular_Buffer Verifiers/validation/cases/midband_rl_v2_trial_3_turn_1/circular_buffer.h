#if !defined(CIRCULAR_BUFFER_H)
#define CIRCULAR_BUFFER_H

#include <algorithm>
#include <cstddef>
#include <stdexcept>
#include <utility>
#include <vector>

namespace circular_buffer {

template <typename ValueType>
class circular_buffer {
public:
    explicit circular_buffer(std::size_t capacity)
        : capacity_(capacity), buffer_(capacity_), head_(0), tail_(0), size_(0) {}

    ValueType read() {
        if (capacity_ == 0 || size_ == 0) {
            throw std::domain_error("buffer is empty");
        }
        ValueType item = std::move(buffer_[head_]);
        head_ = (head_ + 1) % capacity_;
        --size_;
        return item;
    }

    void write(ValueType item) {
        if (capacity_ == 0 || size_ == capacity_) {
            throw std::domain_error("buffer is full");
        }
        buffer_[tail_] = std::move(item);
        tail_ = (tail_ + 1) % capacity_;
        ++size_;
    }

    void overwrite(ValueType item) {
        if (capacity_ == 0) {
            throw std::domain_error("buffer is full");
        }
        if (capacity_ > size_) {
            write(std::move(item));
        } else {
            buffer_[head_] = std::move(item);
            head_ = (head_ + 1) % capacity_;
            tail_ = (tail_ + 1) % capacity_;
        }
    }

    void clear() {
        head_ = 0;
        tail_ = 0;
        size_ = 0;
    }

private:
    std::size_t capacity_;
    std::vector<ValueType> buffer_;
    std::size_t head_;
    std::size_t tail_;
    std::size_t size_;
};

}  // namespace circular_buffer

#endif // CIRCULAR_BUFFER_H
