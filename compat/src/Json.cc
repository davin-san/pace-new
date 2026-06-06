#include "pace_compat/Json.hh"

#include <cctype>
#include <fstream>
#include <sstream>

namespace pace
{

namespace
{

class Parser
{
  public:
    explicit Parser(const std::string& text) : _text(text) {}

    Json parse()
    {
        Json value = parseValue();
        skipWs();
        if (_pos != _text.size()) {
            fail("trailing characters");
        }
        return value;
    }

  private:
    Json parseValue()
    {
        skipWs();
        if (_pos >= _text.size()) {
            fail("unexpected end of input");
        }

        char c = _text[_pos];
        if (c == '{') {
            return Json(parseObject());
        }
        if (c == '[') {
            return Json(parseArray());
        }
        if (c == '"') {
            return Json(parseString());
        }
        if (c == 't') {
            expect("true");
            return Json(true);
        }
        if (c == 'f') {
            expect("false");
            return Json(false);
        }
        if (c == 'n') {
            expect("null");
            return Json(nullptr);
        }
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) {
            return Json(parseNumber());
        }
        fail("invalid value");
        return Json();
    }

    Json::Object parseObject()
    {
        consume('{');
        Json::Object object;
        skipWs();
        if (peek('}')) {
            consume('}');
            return object;
        }

        while (true) {
            skipWs();
            std::string key = parseString();
            skipWs();
            consume(':');
            object.emplace(std::move(key), parseValue());
            skipWs();
            if (peek('}')) {
                consume('}');
                break;
            }
            consume(',');
        }
        return object;
    }

    Json::Array parseArray()
    {
        consume('[');
        Json::Array array;
        skipWs();
        if (peek(']')) {
            consume(']');
            return array;
        }

        while (true) {
            array.push_back(parseValue());
            skipWs();
            if (peek(']')) {
                consume(']');
                break;
            }
            consume(',');
        }
        return array;
    }

    std::string parseString()
    {
        consume('"');
        std::string out;
        while (_pos < _text.size()) {
            char c = _text[_pos++];
            if (c == '"') {
                return out;
            }
            if (c == '\\') {
                if (_pos >= _text.size()) {
                    fail("bad escape");
                }
                char e = _text[_pos++];
                switch (e) {
                  case '"': out.push_back('"'); break;
                  case '\\': out.push_back('\\'); break;
                  case '/': out.push_back('/'); break;
                  case 'b': out.push_back('\b'); break;
                  case 'f': out.push_back('\f'); break;
                  case 'n': out.push_back('\n'); break;
                  case 'r': out.push_back('\r'); break;
                  case 't': out.push_back('\t'); break;
                  default: fail("unsupported escape");
                }
            } else {
                out.push_back(c);
            }
        }
        fail("unterminated string");
        return out;
    }

    double parseNumber()
    {
        size_t begin = _pos;
        if (peek('-')) {
            _pos++;
        }
        while (_pos < _text.size() &&
               std::isdigit(static_cast<unsigned char>(_text[_pos]))) {
            _pos++;
        }
        if (peek('.')) {
            _pos++;
            while (_pos < _text.size() &&
                   std::isdigit(static_cast<unsigned char>(_text[_pos]))) {
                _pos++;
            }
        }
        if (_pos < _text.size() && (_text[_pos] == 'e' || _text[_pos] == 'E')) {
            _pos++;
            if (_pos < _text.size() && (_text[_pos] == '+' || _text[_pos] == '-')) {
                _pos++;
            }
            while (_pos < _text.size() &&
                   std::isdigit(static_cast<unsigned char>(_text[_pos]))) {
                _pos++;
            }
        }
        return std::stod(_text.substr(begin, _pos - begin));
    }

    void skipWs()
    {
        while (_pos < _text.size() &&
               std::isspace(static_cast<unsigned char>(_text[_pos]))) {
            _pos++;
        }
    }

    bool peek(char c) const
    {
        return _pos < _text.size() && _text[_pos] == c;
    }

    void consume(char c)
    {
        skipWs();
        if (!peek(c)) {
            fail(std::string("expected '") + c + "'");
        }
        _pos++;
    }

    void expect(const char* text)
    {
        while (*text) {
            if (_pos >= _text.size() || _text[_pos] != *text) {
                fail("unexpected token");
            }
            _pos++;
            text++;
        }
    }

    [[noreturn]] void fail(const std::string& reason) const
    {
        throw std::runtime_error("json parse error at byte " +
                                 std::to_string(_pos) + ": " + reason);
    }

    const std::string& _text;
    size_t _pos = 0;
};

} // namespace

const Json::Object&
Json::object() const
{
    return std::get<Object>(_value);
}

const Json::Array&
Json::array() const
{
    return std::get<Array>(_value);
}

const std::string&
Json::string() const
{
    return std::get<std::string>(_value);
}

bool
Json::boolean() const
{
    return std::get<bool>(_value);
}

double
Json::number() const
{
    return std::get<double>(_value);
}

const Json&
Json::at(const std::string& key) const
{
    const auto& obj = object();
    auto it = obj.find(key);
    if (it == obj.end()) {
        throw std::runtime_error("missing json key: " + key);
    }
    return it->second;
}

bool
Json::contains(const std::string& key) const
{
    return object().find(key) != object().end();
}

Json
parseJson(const std::string& text)
{
    return Parser(text).parse();
}

Json
parseJsonFile(const std::string& path)
{
    std::ifstream in(path);
    if (!in.is_open()) {
        throw std::runtime_error("could not open json file: " + path);
    }
    std::ostringstream out;
    out << in.rdbuf();
    return parseJson(out.str());
}

} // namespace pace
