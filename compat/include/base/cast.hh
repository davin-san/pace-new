#ifndef __PACE_COMPAT_BASE_CAST_HH__
#define __PACE_COMPAT_BASE_CAST_HH__

namespace gem5
{

template <class T, class U>
inline T
safe_cast(U value)
{
    return dynamic_cast<T>(value);
}

} // namespace gem5

#endif // __PACE_COMPAT_BASE_CAST_HH__
