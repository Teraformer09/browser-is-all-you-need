#pragma once

#include <cmath>
#include <ostream>

namespace complex_numbers {

class Complex {
public:
    Complex(double real, double imaginary);

    Complex operator+(const Complex& other) const;
    Complex operator-(const Complex& other) const;
    Complex operator*(const Complex& other) const;
    Complex operator/(const Complex& other) const;
    double abs() const;
    Complex conj() const;
    double real() const;
    double imag() const;
    Complex exp() const;

    friend bool operator==(const Complex& lhs, const Complex& rhs);
    friend std::ostream& operator<<(std::ostream& os, Complex const& value);
    friend Complex operator+(const Complex& complex, double scalar);
    friend Complex operator+(double scalar, const Complex& complex);
    friend Complex operator-(const Complex& complex, double scalar);
    friend Complex operator-(double scalar, const Complex& complex);
    friend Complex operator*(const Complex& complex, double scalar);
    friend Complex operator*(double scalar, const Complex& complex);
    friend Complex operator/(const Complex& complex, double scalar);
    friend Complex operator/(double scalar, const Complex& complex);

private:
    double real_;
    double imaginary_;
};

}  // namespace complex_numbers
