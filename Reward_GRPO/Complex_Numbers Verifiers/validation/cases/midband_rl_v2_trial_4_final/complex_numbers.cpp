#include "complex_numbers.h"

#include <cmath>

namespace complex_numbers {

Complex::Complex(double real, double imaginary)
    : real_(real), imaginary_(imaginary) {}

Complex Complex::operator+(
    const Complex& other) const {
    return Complex(real_ + other.real_,
                   imaginary_ + other.imaginary_);
}

Complex Complex::operator-(
    const Complex& other) const {
    return Complex(real_ - other.real_,
                   imaginary_ - other.imaginary_);
}

Complex Complex::operator*(
    const Complex& other) const {
    return Complex(
        real_ * other.real_ - imaginary_ * other.imaginary_,
        real_ * other.imaginary_ + imaginary_ * other.real_);
}

Complex Complex::operator/(
    const Complex& other) const {
    const double denominator =
        other.real_ * other.real_ +
        other.imaginary_ * other.imaginary_;
    return Complex(
        (real_ * other.real_ + imaginary_ * other.imaginary_) /
            denominator,
        (imaginary_ * other.real_ - real_ * other.imaginary_) /
            denominator);
}

double Complex::abs() const {
    return std::hypot(real_, imaginary_);
}

Complex Complex::conj() const {
    return Complex(real_, -imaginary_);
}

double Complex::real() const { return real_; }
double Complex::imag() const { return imaginary_; }

Complex Complex::exp() const {
    const double scale = std::exp(real_);
    return Complex(scale * std::cos(imaginary_),
                   scale * std::sin(imaginary_));
}

bool operator==(const Complex& lhs,
                const Complex& rhs) {
    return lhs.real_ == rhs.real_ &&
           lhs.imaginary_ == rhs.imaginary_;
}

std::ostream& operator<<(
    std::ostream& os, Complex const& value) {
    os << value.real_ << " + " << value.imaginary_ << "i";
    return os;
}

Complex operator+(const Complex& complex,
                   double scalar) {
    return Complex(complex.real_ + scalar,
                   complex.imaginary_);
}

Complex operator+(double scalar,
                   const Complex& complex) {
    return complex + scalar;
}

Complex operator-(const Complex& complex,
                   double scalar) {
    return Complex(complex.real_ - scalar,
                   complex.imaginary_);
}

Complex operator-(double scalar,
                   const Complex& complex) {
    return Complex(scalar - complex.real_,
                   -complex.imaginary_);
}

Complex operator*(const Complex& complex,
                   double scalar) {
    return Complex(complex.real_ * scalar,
                   complex.imaginary_ * scalar);
}

Complex operator*(double scalar,
                   const Complex& complex) {
    return complex * scalar;
}

Complex operator/(const Complex& complex,
                   double scalar) {
    return Complex(complex.real_ / scalar,
                   complex.imaginary_ / scalar);
}

Complex operator/(double scalar,
                   const Complex& complex) {
    const double denominator =
        complex.real_ * complex.real_ +
        complex.imaginary_ * complex.imaginary_;
    return Complex(scalar * complex.real_ / denominator,
                   -scalar * complex.imaginary_ / denominator);
}

}  // namespace complex_numbers
