cmake_minimum_required(VERSION 3.16)
project(ScopeControllerCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBUSB REQUIRED libusb-1.0)

if(NOT LIBUSB_FOUND)
    message(FATAL_ERROR
        "ไม่พบ libusb-1.0 — ติดตั้งด้วย: sudo apt install libusb-1.0-0-dev pkg-config"
    )
endif()

message(STATUS "libusb include: ${LIBUSB_INCLUDE_DIRS}")
message(STATUS "libusb library: ${LIBUSB_LIBRARIES}")

# AUTOMOC ต้องเห็นไฟล์ที่มี Q_OBJECT โดยตรงในลิสต์ source files ถึงจะ
# generate moc code ให้ — แค่ #include เข้า main.cpp ไม่พอ (Qt meta-object
# system มองไม่เห็น) จึงต้องเพิ่มไฟล์ .cpp ที่มี Q_OBJECT เข้ามาตรงนี้ด้วย
# แต่ทำเครื่องหมาย HEADER_FILE_ONLY เพื่อไม่ให้ CMake compile มันแยกต่างหาก
# (ป้องกัน "multiple definition" เพราะ main.cpp include เนื้อหาเดียวกันอยู่แล้ว)
set(QOBJECT_SOURCES
    gui_cpp/waveform_widget.cpp
    gui_cpp/workspace_tab.cpp
    gui_cpp/tools_tab.cpp
    gui_cpp/app.cpp
)
set_source_files_properties(${QOBJECT_SOURCES} PROPERTIES HEADER_FILE_ONLY ON)

add_executable(ScopeControllerCpp
    main.cpp
    ${QOBJECT_SOURCES}
)

target_include_directories(ScopeControllerCpp PRIVATE ${LIBUSB_INCLUDE_DIRS})
target_link_libraries(ScopeControllerCpp PRIVATE
    Qt6::Widgets
    ${LIBUSB_LIBRARIES}
)
target_compile_options(ScopeControllerCpp PRIVATE ${LIBUSB_CFLAGS_OTHER})
