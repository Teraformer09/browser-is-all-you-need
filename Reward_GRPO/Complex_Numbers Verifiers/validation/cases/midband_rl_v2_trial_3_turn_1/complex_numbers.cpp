#include "complex_numbers.h"

#include <cmath>

namespace complex_numbers {

Complex::Complex(double real, double imaginary)
    : real_(real), imag_(imaginary) {}

Complex Complex::operator+(
    const Complex& other) const {
    return Complex(real_ + other.real_,
                   imag_ + other.imag_);
}

Complex Complex::operator-(
    const Complex& other) const {
    return Complex(real_ - other.real_,
                   imag_ - other.imag_);
}

Complex Complex::operator*(
    const Complex& other) const {
    return Complex(
        real_ * other.real_ - imag_ * other.imag_,
        real_ * other.imag_ + imag_ * other.real_);
}

Complex Complex::operator/(
    const Complex& other) const {
    const double denominator =
        other.real_ * other.real_ +
        other.imag_ * other.imag_;
    return Complex(
        (real_ * other.real_ + imag_ * other.imag_) /
            denominator,
        (imag_ * other.real_ - real_ * other.imag_) /
            denominator);
}

double Complex::abs() const {
    return std::hypot(real_, imag_);
}

Complex Complex::conj() const {
    return Complex(real_, -imag_);
}

double Complex::real() const {
    return real_;
}

double Complex::imag() const {
    return imag_;
}

Complex Complex::exp() const {
    const double scale = std::exp(real_);
    return Complex(scale * std::cos(imag_),
                   scale * std::sin(imag_));
}

bool operator==(const Complex& lhs,
                const Complex& rhs) {
    const double tolerance = 1e-9;
    return std::abs(lhs.real_ - rhs.real_) <= tolerance &&
           std::abs(lhs.imag_ - rhs.imag_) <= tolerance;
}

std::ostream& operator<<(
    std::ostream& os, Complex const& value) {
    const double real = value.real_;
    const double imag = value.imag_;
    if (imag >= 0) {
        os << real << " + " << imag << "i";
    } else {
        os << real << " - " << -imag << "i";
    }
    return os;
}

Complex operator+(
    const Complex& complex, double scalar) {
    return Complex(complex.real_ + scalar,
                   complex.imag_);
}

Complex operator+(
    double scalar, const Complex& complex) {
    return complex + scalar;
}

Complex operator-(
    const Complex& complex, double scalar) {
    return Complex(complex.real_ - scalar,
                   complex.imag_);
}

Complex operator-(
    double scalar, const Complex& complex) {
    return Complex(scalar - complex.real_,
                   -complex.imag_);
}

Complex operator*(
    const Complex& complex, double scalar) {
    return Complex(complex.real_ * scalar,
                   complex.imag_ * scalar);
}

Complex operator*(
    double scalar, const Complex& complex) {
    return complex * scalar;
}

Complex operator/(
    const Complex& complex, double scalar) {
    return Complex(complex.real_ / scalar,
                   complex.imag_ / scalar);
}

Complex operator/(
    double scalar, const Complex& complex) {
    const double denominator =
        complex.real_ * complex.real_ +
        complex.imag_ * complex.imag_;
    return Complex(
        scalar * complex.real_ / denominator,
        -scalar * complex.imag_ / denominator);
}

}  // namespace complex_numbers
