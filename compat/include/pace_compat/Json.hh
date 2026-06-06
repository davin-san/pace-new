#ifndef __PACE_COMPAT_JSON_HH__
#define __PACE_COMPAT_JSON_HH__

#include <map>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

namespace pace
{

class Json
{
  public:
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    using Value = std::variant<std::nullptr_t, bool, double, std::string,
                               Array, Object>;

    Json() : _value(nullptr) {}
    explicit Json(Value value) : _value(std::move(value)) {}

    bool isNull() const { return std::holds_alternative<std::nullptr_t>(_value); }
    bool isObject() const { return std::holds_alternative<Object>(_value); }
    bool isArray() const { return std::holds_alternative<Array>(_value); }
    bool isString() const { return std::holds_alternative<std::string>(_value); }
    bool isBool() const { return std::holds_alternative<bool>(_value); }
    bool isNumber() const { return std::holds_alternative<double>(_value); }

    const Object& object() const;
    const Array& array() const;
    const std::string& string() const;
    bool boolean() const;
    double number() const;

    const Json& at(const std::string& key) const;
    bool contains(const std::string& key) const;

  private:
    Value _value;
};

Json parseJson(const std::string& text);
Json parseJsonFile(const std::string& path);

} // namespace pace

#endif // __PACE_COMPAT_JSON_HH__
