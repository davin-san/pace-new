#ifndef __PACE_COMPAT_STATS_HH__
#define __PACE_COMPAT_STATS_HH__

#include <string>
#include <vector>
#include <cstdio>

namespace gem5
{
namespace statistics
{

enum Flags
{
    nozero = 1 << 0,
    pdf = 1 << 1,
    total = 1 << 2,
    oneline = 1 << 3
};

class Scalar
{
  public:
    Scalar& name(const std::string&) { return *this; }
    Scalar& flags(int) { return *this; }
    Scalar& operator=(double value) { _value = value; return *this; }
    Scalar& operator+=(double value) { _value += value; return *this; }
    Scalar& operator++(int) { _value += 1; return *this; }
    operator double() const { return _value; }

  private:
    double _value = 0;
};

class Vector
{
  public:
    Vector& init(size_t size) { _values.assign(size, 0); return *this; }
    Vector& name(const std::string&) { return *this; }
    Vector& flags(int) { return *this; }
    Vector& subname(size_t, const std::string&) { return *this; }

    double& operator[](size_t index)
    {
        if (index >= _values.size()) {
            _values.resize(index + 1, 0);
        }
        return _values[index];
    }

    double operator[](size_t index) const
    {
        return index < _values.size() ? _values[index] : 0;
    }

    size_t size() const { return _values.size(); }
    const std::vector<double>& values() const { return _values; }

  private:
    std::vector<double> _values;
};

class Formula
{
  public:
    Formula& name(const std::string&) { return *this; }
    Formula& flags(int) { return *this; }

    template <class T>
    Formula& operator=(const T&) { return *this; }

    operator double() const { return 0; }
};

inline double sum(const Vector& vector)
{
    double total = 0;
    for (double value : vector.values()) {
        total += value;
    }
    return total;
}

inline Formula operator/(const Vector&, const Vector&) { return Formula(); }
inline Formula operator+(const Formula&, const Formula&) { return Formula(); }
inline Formula operator/(const Scalar&, double) { return Formula(); }

} // namespace statistics

inline std::string
csprintf(const char* fmt, int value)
{
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), fmt, value);
    return buffer;
}

} // namespace gem5

#endif // __PACE_COMPAT_STATS_HH__
