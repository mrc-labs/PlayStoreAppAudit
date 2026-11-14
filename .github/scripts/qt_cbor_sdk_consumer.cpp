// Exercise only the already-built QtCore/TinyCBOR provider; no framework rebuild.
#include <QtCore/QBuffer>
#include <QtCore/QCborArray>
#include <QtCore/QCborMap>
#include <QtCore/QCborStreamReader>
#include <QtCore/QCborStreamWriter>
#include <QtCore/QCborValue>
#include <QtCore/QCoreApplication>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QTextStream>
#include <cstdlib>

static void require(bool ok, const char *message) {
    if (!ok) { QTextStream(stderr) << message << Qt::endl; std::exit(1); }
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    require(QString::fromLatin1(qVersion()) == "6.12.0", "Wrong Qt runtime");
    QCborMap map;
    map.insert(QStringLiteral("integer"), 42);
    map.insert(QStringLiteral("text"), QString::fromUtf8("caf\xc3\xa8"));
    map.insert(QStringLiteral("array"), QCborArray{true, nullptr, -12});
    const QCborValue expected(map);
    const QByteArray encoded = expected.toCbor();
    QCborParserError error;
    require(QCborValue::fromCbor(encoded, &error) == expected && error.error.c == QCborError::NoError,
        "Memory roundtrip failed");
    QBuffer input;
    input.setData(encoded);
    require(input.open(QIODevice::ReadOnly), "Input device failed");
    QCborStreamReader reader(&input);
    require(QCborValue::fromCbor(reader) == expected && reader.lastError().c == QCborError::NoError,
        "Device callbacks failed");
    QByteArray bytes;
    QBuffer output(&bytes);
    require(output.open(QIODevice::WriteOnly), "Output device failed");
    QCborStreamWriter writer(&output);
    writer.startMap(1); writer.append(QStringLiteral("value")); writer.append(42);
    require(writer.endMap(), "Device writer failed");
    output.close();
    require(QCborValue::fromCbor(bytes).toMap().value(QStringLiteral("value")).toInteger() == 42,
        "Device writer roundtrip failed");
    struct Negative { const char *hex; qint64 offset; QCborError::Code error; };
    QJsonArray negatives;
    for (const auto &test : {Negative{"1b00", 0, QCborError::EndOfFile},
                            Negative{"bf6161", 3, QCborError::EndOfFile},
                            Negative{"ff", 0, QCborError::UnexpectedBreak},
                            Negative{"8201", 2, QCborError::EndOfFile}}) {
        QCborValue::fromCbor(QByteArray::fromHex(test.hex), &error);
        // A partial value can be returned; its explicit parser error is authoritative.
        require(error.error.c == test.error && error.offset == test.offset, "Wrong parser error/offset");
        negatives.append(QJsonObject{{"input", test.hex}, {"error", int(error.error.c)}, {"offset", error.offset}});
    }
    QFile maps("/proc/self/maps");
    require(maps.open(QIODevice::ReadOnly), "Cannot inspect loaded images");
    QJsonArray loaded;
    for (const auto &line : maps.readAll().split('\n'))
        if (line.contains('/')) loaded.append(QString::fromUtf8(line));
    QJsonObject result{{"qt", qVersion()}, {"roundtrip", true}, {"qiodevice_read_write", true},
        {"negative", negatives}, {"loaded", loaded}, {"result", "PASS retained QtCore CBOR memory/device/parser regressions"}};
    QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
}
