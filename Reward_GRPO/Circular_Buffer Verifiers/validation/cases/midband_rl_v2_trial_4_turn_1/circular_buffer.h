#if !defined(CIRCULAR_BUFFER_H)
#define CIRCULAR_BUFFER_H

#include <cstddef>
#include <stdexcept>
#include <vector>

namespace circular_buffer {

template <typename ValueType>
class circular_buffer {
public:
    circular_buffer(std::size_t capacity)
        : capacity_(capacity), capacity_vector_(capacity), head_(0), tail_(0), count_(0) {}

    ValueType read() {
        if (count_ == 0) {
            throw std::domain_error("buffer is empty");
        }
        ValueType value = capacity_vector_[head_];
        head_ = (head_ + 1) % capacity_;
        --count_;
        return value;
    }

    void write(ValueType item) {
        if (count_ == capacity_) {
            throw std::domain_error("buffer is full");
        }
        capacity_vector_[tail_] = item;
        tail_ = (tail_ + 1) % capacity_;
        ++count_;
    }

    void overwrite(ValueType item) {
        if (count_ == capacity_) {
            capacity_vector_[head_] = item;
            head_ = (head_ + 1) % capacity_;
        } else {
            capacity_vector_[tail_] = item;
            tail_ = (tail_ + 1) % capacity_;
        }
        ++count_;
    }

    void clear() {
        head_ = 0;
        tail_ = 0;
        count_ = 0;
    }

private:
    std::size_t capacity_;
    std::vector<ValueType> capacity_vector_;
    std::size_t head_;
    std::size_t tail_;
    std::size_t count_;
};

}  // namespace circular_buffer

#endif // CIRCULAR_BUFFER_H
