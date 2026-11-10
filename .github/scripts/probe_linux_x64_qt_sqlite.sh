#!/usr/bin/env bash
# Exercise the supported system-SQLite Qt driver, not only its configure flag.
set -euo pipefail
work=${PILOT_WORK:?}
evidence=${PILOT_EVIDENCE:?}
prefix="$work/prefix"
probe="$work/qt-sqlite-probe"
mkdir -p "$probe"
cat > "$probe/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.25)
project(ControlledQtSqlite LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Sql)
add_executable(probe main.cpp)
target_link_libraries(probe PRIVATE Qt6::Core Qt6::Sql)
CMAKE
cat > "$probe/main.cpp" <<'CPP'
#include <QCoreApplication>
#include <QLibraryInfo>
#include <QSqlDatabase>
#include <QSqlError>
#include <QSqlQuery>
#include <QVariant>
#include <iostream>
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");
    db.setDatabaseName(":memory:");
    if (!db.open()) { std::cerr << db.lastError().text().toStdString(); return 1; }
    QSqlQuery query(db);
    if (!query.exec("select sqlite_version()") || !query.next()) return 2;
    if (query.value(0).toString() != "3.54.1") return 3;
    std::cout << "Qt " << qVersion() << " actual SQLite " << query.value(0).toString().toStdString()
              << " libraries " << QLibraryInfo::path(QLibraryInfo::LibrariesPath).toStdString() << " PASS\n";
    return 0;
}
CPP
cmake -S "$probe" -B "$probe/build" -GNinja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$prefix/qt;$prefix" -DCMAKE_BUILD_RPATH="$prefix/qt/lib;$prefix/lib" \
  > "$evidence/qt-sqlite-configure.log" 2>&1 || { tail -n 80 "$evidence/qt-sqlite-configure.log"; exit 1; }
cmake --build "$probe/build" > "$evidence/qt-sqlite-build.log" 2>&1 || { tail -n 80 "$evidence/qt-sqlite-build.log"; exit 1; }
QT_PLUGIN_PATH="$prefix/qt/plugins" LD_LIBRARY_PATH="$prefix/qt/lib:$prefix/lib:$LD_LIBRARY_PATH" \
  "$probe/build/probe" > "$evidence/qt-sqlite-consumer.log" 2>&1 || { cat "$evidence/qt-sqlite-consumer.log"; exit 1; }
grep -F 'Qt 6.12.0 actual SQLite 3.54.1' "$evidence/qt-sqlite-consumer.log"
ldd "$prefix/qt/plugins/sqldrivers/libqsqlite.so" > "$evidence/qt-sqlite-plugin-ldd.txt"
grep -F "$prefix/lib/libsqlite3.so" "$evidence/qt-sqlite-plugin-ldd.txt"
cp "$probe/build/probe" "$evidence/qt-sqlite-consumer"
cp "$probe/main.cpp" "$evidence/qt-sqlite-consumer.cpp"
