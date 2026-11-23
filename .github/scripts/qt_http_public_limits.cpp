// Real release QtNetwork parser, through public API; the peer never closes early.
#include <QtCore/QCoreApplication>
#include <QtCore/QEventLoop>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QTextStream>
#include <QtCore/QTimer>
#include <QtNetwork/QHostAddress>
#include <QtNetwork/QNetworkAccessManager>
#include <QtNetwork/QNetworkProxy>
#include <QtNetwork/QNetworkReply>
#include <QtNetwork/QNetworkRequest>
#include <QtNetwork/QTcpServer>
#include <QtNetwork/QTcpSocket>
#include <memory>

struct Case { const char *name; QByteArray payload; bool accept; qsizetype chunk; };

static QJsonObject exercise(const Case &test)
{
    QTcpServer server;
    const bool listening = server.listen(QHostAddress::LocalHost, 0);
    QNetworkAccessManager manager;
    manager.setProxy(QNetworkProxy::NoProxy);
    QEventLoop loop;
    qint64 sent = 0;
    bool connected = false, timedOut = false;
    QObject::connect(&server, &QTcpServer::newConnection, &loop, [&] {
        while (server.hasPendingConnections()) {
            auto *socket = server.nextPendingConnection();
            auto request = std::make_shared<QByteArray>();
            auto handled = std::make_shared<bool>(false);
            QObject::connect(socket, &QTcpSocket::readyRead, &loop, [&, socket, request, handled] {
                request->append(socket->readAll());
                if (*handled || !request->contains("\r\n\r\n")) return;
                *handled = true;
                connected = true;
                if (test.chunk == 0) {
                    sent += socket->write(test.payload);
                } else {
                    auto offset = std::make_shared<qsizetype>(0);
                    auto *pieces = new QTimer(socket);
                    QObject::connect(pieces, &QTimer::timeout, socket, [&, socket, pieces, offset] {
                        if (socket->state() != QAbstractSocket::ConnectedState || *offset >= test.payload.size()) {
                            pieces->stop();
                            return;
                        }
                        const auto bytes = test.payload.mid(*offset, test.chunk);
                        sent += socket->write(bytes);
                        *offset += bytes.size();
                    });
                    pieces->start(1);
                }
                // Keep the server side open, including unterminated responses.
            });
        }
    });
    QNetworkRequest request{QUrl(QString("http://127.0.0.1:%1/").arg(server.serverPort()))};
    request.setAttribute(QNetworkRequest::Http2AllowedAttribute, false);
    request.setTransferTimeout(8000);
    auto *reply = manager.get(request);
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    QTimer deadline;
    deadline.setSingleShot(true);
    QObject::connect(&deadline, &QTimer::timeout, &loop, [&] { timedOut = true; reply->abort(); loop.quit(); });
    deadline.start(10000);
    loop.exec();
    const auto body = reply->readAll();
    const auto error = reply->error();
    const bool ordinary = error == QNetworkReply::NoError && body == "OK"
        && reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 200;
    const bool refusal = error != QNetworkReply::NoError && error != QNetworkReply::TimeoutError
        && error != QNetworkReply::OperationCanceledError && body.isEmpty();
    const bool ok = listening && connected && sent > 0 && !timedOut && (test.accept ? ordinary : refusal);
    QJsonObject row{{"name", test.name}, {"result", ok ? "PASS" : "FAIL"}, {"expected_accept", test.accept},
        {"error_code", int(error)}, {"error", reply->errorString()}, {"timed_out", timedOut},
        {"server_initiated_close", false}, {"response_bytes_queued", sent}, {"body_bytes", qint64(body.size())}};
    delete reply;
    return row;
}

int main(int argc, char **argv)
{
    QCoreApplication application(argc, argv);
    if (QString::fromLatin1(qVersion()) != "6.12.0") return 2;
    const QByteArray ordinary = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK";
    const QByteArray large = QByteArray("HTTP/1.1 200 OK\r\nX-Large: ") + QByteArray(96 * 1024, 'a')
        + "\r\nContent-Length: 2\r\n\r\nOK";
    const QByteArray oversized = QByteArray("HTTP/1.1 200 OK\r\nX-A: ") + QByteArray(96 * 1024, 'a')
        + "\r\nX-B: " + QByteArray(96 * 1024, 'b') + "\r\nX-C: " + QByteArray(96 * 1024, 'c');
    const QByteArray status = QByteArray("HTTP/1.1 200 ") + QByteArray(1500, 'r');
    const Case cases[] = {
        {"ordinary", ordinary, true, 0}, {"ordinary-fragmented", ordinary, true, 3},
        {"under-field-and-total-limits", large, true, 0},
        {"under-limit-fragmented", large, true, 4096},
        {"status-over-limit-terminated", status + "\r\nContent-Length: 0\r\n\r\n", false, 0},
        {"status-over-limit-unterminated", status, false, 0},
        {"status-over-limit-fragmented", status, false, 97},
        {"headers-over-total-terminated", oversized + "\r\nContent-Length: 0\r\n\r\n", false, 0},
        {"headers-over-total-unterminated", oversized, false, 0},
        {"headers-over-total-fragmented", oversized, false, 4096},
    };
    QJsonArray results;
    bool ok = true;
    for (const auto &test : cases) {
        const auto result = exercise(test);
        ok = ok && result["result"].toString() == "PASS";
        results.append(result);
    }
    QTextStream(stdout) << QJsonDocument(QJsonObject{{"qt", qVersion()}, {"cases", results},
        {"scope", "Public release QtNetwork runtime; timeout/client-abort/server-EOF never count as rejection"},
        {"result", ok ? "PASS" : "FAIL"}}).toJson(QJsonDocument::Compact) << Qt::endl;
    return ok ? 0 : 1;
}
