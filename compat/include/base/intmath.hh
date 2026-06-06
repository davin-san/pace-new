#ifndef __PACE_COMPAT_BASE_INTMATH_HH__
#define __PACE_COMPAT_BASE_INTMATH_HH__

#include <cmath>

namespace gem5
{

template <class T, class U>
inline auto
divCeil(T a, U b)
{
    return (decltype(a + b))std::ceil((double)a / (double)b);
}

} // namespace gem5

#endif // __PACE_COMPAT_BASE_INTMATH_HH__
