#include "pace_compat/Trace.hh"

#include <cstdarg>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "base/types.hh"

namespace pace
{

namespace
{

std::ofstream trace_stream;
constexpr const char* trace_printf_prefix = "PACE_TRACE ";

std::string
escapeJson(const std::string& value)
{
    std::string out;
    out.reserve(value.size() + 2);
    for (char c : value) {
        switch (c) {
          case '\\': out += "\\\\"; break;
          case '"': out += "\\\""; break;
          case '\b': out += "\\b"; break;
          case '\f': out += "\\f"; break;
          case '\n': out += "\\n"; break;
          case '\r': out += "\\r"; break;
          case '\t': out += "\\t"; break;
          default: out.push_back(c); break;
        }
    }
    return out;
}

} // namespace

void
setTraceFile(const std::string& path)
{
    closeTraceFile();
    trace_stream.open(path);
    if (!trace_stream.is_open()) {
        throw std::runtime_error("could not open trace file: " + path);
    }
}

void
closeTraceFile()
{
    if (trace_stream.is_open()) {
        trace_stream.close();
    }
}

bool
traceEnabled()
{
    return trace_stream.is_open();
}

void
traceEvent(const std::string& event, TraceFields fields)
{
    if (!traceEnabled()) {
        return;
    }

    trace_stream << "{\"tick\":" << gem5::curTick()
                 << ",\"event\":\"" << escapeJson(event) << "\"";
    for (const auto& field : fields) {
        trace_stream << ",\"" << escapeJson(field.first) << "\":"
                     << field.second;
    }
    trace_stream << "}\n";
}

void
tracePrintf(const char*, const char* format, ...)
{
    if (!traceEnabled() || format == nullptr) {
        return;
    }

    const std::string fmt(format);
    if (fmt.rfind(trace_printf_prefix, 0) != 0) {
        return;
    }

    va_list args;
    va_start(args, format);
    va_list args_copy;
    va_copy(args_copy, args);
    const int needed = std::vsnprintf(nullptr, 0, format, args_copy);
    va_end(args_copy);
    if (needed < 0) {
        va_end(args);
        return;
    }

    std::vector<char> buffer(static_cast<size_t>(needed) + 1);
    std::vsnprintf(buffer.data(), buffer.size(), format, args);
    va_end(args);

    std::string formatted(buffer.data(), static_cast<size_t>(needed));
    std::string payload = formatted.substr(std::char_traits<char>::length(
        trace_printf_prefix));
    while (!payload.empty() &&
           (payload.back() == '\n' || payload.back() == '\r')) {
        payload.pop_back();
    }
    trace_stream << payload << "\n";
}

std::string
traceValue(const std::string& value)
{
    return "\"" + escapeJson(value) + "\"";
}

std::string
traceValue(const char* value)
{
    return traceValue(std::string(value ? value : ""));
}

std::string
traceValue(bool value)
{
    return value ? "true" : "false";
}

} // namespace pace
