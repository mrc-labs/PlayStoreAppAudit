// Bounded Qt Network HTTP/TLS smoke. No explicit CA, ignored errors or store changes.
#include <QtCore/QCoreApplication>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QTextStream>
#include <QtCore/QTimer>
#include <QtNetwork/QNetworkAccessManager>
#include <QtNetwork/QNetworkProxy>
#include <QtNetwork/QNetworkReply>
#include <QtNetwork/QNetworkRequest>
#include <QtNetwork/QSslConfiguration>
#include <QtNetwork/QSslSocket>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (QString::fromLatin1(qVersion()) != "6.12.0"
        || !QSslSocket::setActiveBackend("openssl")
        || !QSslSocket::sslLibraryVersionString().startsWith("OpenSSL 4.0.3 "))
        return 2;
    QNetworkAccessManager manager;
    manager.setProxy(QNetworkProxy::NoProxy);
    QNetworkRequest request(QUrl("https://www.python.org/"));
    // Exercise the changed HTTP/1 response parser over authenticated default TLS.
    request.setAttribute(QNetworkRequest::Http2AllowedAttribute, false);
    request.setTransferTimeout(20000);
    auto *reply = manager.get(request);
    bool sslErrors = false, timedOut = false;
    QObject::connect(reply, &QNetworkReply::sslErrors, [&sslErrors] { sslErrors = true; });
    QObject::connect(reply, &QNetworkReply::finished, &app, &QCoreApplication::quit);
    QTimer timer;
    timer.setSingleShot(true);
    QObject::connect(&timer, &QTimer::timeout, [&] { timedOut = true; reply->abort(); app.quit(); });
    timer.start(30000);
    app.exec();
    const auto config = reply->sslConfiguration();
    const bool ok = !timedOut && !sslErrors && reply->error() == QNetworkReply::NoError
        && reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 200
        && !reply->readAll().isEmpty() && !config.peerCertificate().isNull()
        && (config.peerVerifyMode() == QSslSocket::VerifyPeer || config.peerVerifyMode() == QSslSocket::AutoVerifyPeer)
        && !reply->attribute(QNetworkRequest::Http2WasUsedAttribute).toBool();
    QFile maps("/proc/self/maps");
    if (!maps.open(QIODevice::ReadOnly)) return 3;
    QJsonArray loaded;
    for (const auto &line : maps.readAll().split('\n'))
        if (line.contains('/'))
            loaded.append(QString::fromUtf8(line));
    QJsonObject result{{"result", ok ? "PASS default-trust authenticated HTTP/1 response" : "FAIL"},
        {"qt", qVersion()}, {"backend", QSslSocket::activeBackend()},
        {"openssl", QSslSocket::sslLibraryVersionString()}, {"ssl_errors", sslErrors},
        {"error", reply->errorString()}, {"default_ca_count", config.caCertificates().size()},
        {"peer_verify_mode", int(config.peerVerifyMode())}, {"loaded", loaded}};
    QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
    return ok ? 0 : 1;
}
