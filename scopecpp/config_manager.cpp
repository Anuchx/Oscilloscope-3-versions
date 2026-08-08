// config_manager.cpp
// Save/Load configuration: read and write scope settings as JSON.
// Mirrors config_manager.py. Uses a minimal hand-rolled JSON writer/reader
// for simple flat string-keyed maps — avoids pulling in an external JSON
// library dependency for something this small.

#pragma once

#include <string>
#include <map>
#include <fstream>
#include <sstream>
#include <stdexcept>

// เก็บค่าตั้งค่าทั้งหมดเป็น string ธรรมดา (ฝั่งเรียกใช้แปลงเป็น int/double/bool เอง)
// ทำให้ JSON writer/reader ง่ายมาก ไม่ต้องรองรับ type หลากหลาย
using ConfigMap = std::map<std::string, std::string>;

inline void saveConfig(const std::string& path, const ConfigMap& settings) {
    std::ofstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file for writing: " + path);
    }

    file << "{\n";
    size_t i = 0;
    for (const auto& pair : settings) {
        file << "  \"" << pair.first << "\": \"" << pair.second << "\"";
        if (++i < settings.size()) file << ",";
        file << "\n";
    }
    file << "}\n";
}

inline ConfigMap loadConfig(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file for reading: " + path);
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    ConfigMap result;

    // parser ง่ายๆ สำหรับ JSON แบบแบน {"key": "value", ...} เท่านั้น
    // ไม่รองรับ nested object/array เพราะ config ของเราไม่มี structure ซับซ้อนขนาดนั้น
    size_t pos = 0;
    while (true) {
        size_t keyStart = content.find('"', pos);
        if (keyStart == std::string::npos) break;
        size_t keyEnd = content.find('"', keyStart + 1);
        if (keyEnd == std::string::npos) break;
        std::string key = content.substr(keyStart + 1, keyEnd - keyStart - 1);

        size_t colonPos = content.find(':', keyEnd);
        if (colonPos == std::string::npos) break;

        size_t valueStart = content.find('"', colonPos);
        if (valueStart == std::string::npos) break;
        size_t valueEnd = content.find('"', valueStart + 1);
        if (valueEnd == std::string::npos) break;
        std::string value = content.substr(valueStart + 1, valueEnd - valueStart - 1);

        result[key] = value;
        pos = valueEnd + 1;
    }

    return result;
}
