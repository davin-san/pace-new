#ifndef __PACE_COMPAT_TRACE_HH__
#define __PACE_COMPAT_TRACE_HH__

#include <initializer_list>
#include <string>
#include <utility>

namespace pace
{

using TraceFields = std::initializer_list<std::pair<std::string, std::string>>;

void setTraceFile(const std::string& path);
void closeTraceFile();
bool traceEnabled();
void traceEvent(const std::string& event, TraceFields fields = {});
void tracePrintf(const char* flag, const char* format, ...);

std::string traceValue(const std::string& value);
std::string traceValue(const char* value);
std::string traceValue(bool value);

template <class T>
std::string
traceValue(T value)
{
    return std::to_string(value);
}

} // namespace pace

#endif // __PACE_COMPAT_TRACE_HH__
