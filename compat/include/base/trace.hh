#ifndef __PACE_COMPAT_BASE_TRACE_HH__
#define __PACE_COMPAT_BASE_TRACE_HH__

#ifdef PACE_ENABLE_DPRINTF_TRACE
#include "pace_compat/Trace.hh"
#define DPRINTF(flag, ...) pace::tracePrintf(#flag, __VA_ARGS__)
#else
#define DPRINTF(flag, ...) do {} while (0)
#endif

#endif // __PACE_COMPAT_BASE_TRACE_HH__
