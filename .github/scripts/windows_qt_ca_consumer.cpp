// Bounded native Schannel diagnostic. Never installs roots or ignores TLS errors.
#include <QtCore/QCoreApplication>
#include <QtCore/QCryptographicHash>
#include <QtCore/QDateTime>
#include <QtCore/QDir>
#include <QtCore/QDirIterator>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QSet>
#include <QtCore/QSysInfo>
#include <QtCore/QTextStream>
#include <QtNetwork/QSslCertificate>
#include <QtNetwork/QSslConfiguration>
#include <QtNetwork/QSslKey>
#include <QtNetwork/QSslSocket>
#include <windows.h>
#include <psapi.h>
#include <stdexcept>

static void require(bool value, const char *message)
{
    if (!value) throw std::runtime_error(message);
}
static QByteArray bytes(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "input unreadable");
    return file.readAll();
}
static QString sha(const QByteArray &data)
{
    return QString::fromLatin1(QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex());
}
static QJsonArray errorsJson(const QList<QSslError> &errors)
{
    QJsonArray result;
    for (const auto &error : errors)
        result.append(QJsonObject{{"code", int(error.error())}, {"text", error.errorString()}});
    return result;
}
static QJsonArray loadedModules()
{
    HMODULE modules[4096]; DWORD needed = 0;
    require(K32EnumProcessModules(GetCurrentProcess(), modules, sizeof modules, &needed), "module enumeration failed");
    require(needed <= sizeof modules, "module list truncated");
    QJsonArray result;
    for (size_t i = 0; i < needed / sizeof(HMODULE); ++i) {
        wchar_t name[32768];
        DWORD size = GetModuleFileNameW(modules[i], name, 32768);
        require(size > 0 && size < 32768, "module path unavailable");
        result.append(QString::fromWCharArray(name, int(size)));
    }
    return result;
}
static QJsonObject policy(const QString &root)
{
    QSet<QString> badKeys;
    QJsonArray keyChecks, chains, rootChecks;
    const auto metadata = QJsonDocument::fromJson(bytes(root + "/impacted-intermediates.json")).array();
    require(metadata.size() == 16, "metadata count changed");
    for (const auto &entry : metadata) {
        const auto item = entry.toObject();
        const auto certs = QSslCertificate::fromData(item["pem"].toString().toUtf8());
        require(certs.size() == 1, "metadata certificate invalid");
        const auto &cert = certs[0];
        const auto key = sha(cert.publicKey().toDer());
        require(sha(cert.toDer()) == item["sha256"].toString().toLower(), "certificate fingerprint differs");
        require(key == item["spki_sha256"].toString().toLower(), "SPKI encoding differs");
        require(cert.isBlacklisted(), "compromised key not blacklisted");
        badKeys.insert(key);
        keyChecks.append(QJsonObject{{"certificate", sha(cert.toDer())}, {"spki", key}, {"blacklisted", true}});
    }
    require(badKeys.size() == 8, "incident key count changed");
    const auto roots = QJsonDocument::fromJson(bytes(root + "/roots.json")).array();
    require(roots.size() == 4, "healthy root count changed");
    for (const auto &entry : roots) {
        const auto certs = QSslCertificate::fromData(entry.toObject()["pem"].toString().toUtf8());
        require(certs.size() == 1 && !certs[0].isBlacklisted(), "healthy root overblocked");
        rootChecks.append(sha(certs[0].toDer()));
    }
    QDirIterator files(root + "/chains", {"*.pem"}, QDir::Files, QDirIterator::Subdirectories);
    bool rollover = false;
    while (files.hasNext()) {
        const auto path = files.next();
        const auto chain = QSslCertificate::fromData(bytes(path));
        require(chain.size() >= 2, "chain truncated");
        QSet<QByteArray> badCerts, actualBadCerts;
        QJsonArray positions;
        for (qsizetype i = 0; i < chain.size(); ++i) {
            require(chain[i].effectiveDate() <= QDateTime::currentDateTimeUtc()
                && chain[i].expiryDate() > QDateTime::currentDateTimeUtc(), "fixture validity expired");
            if (badKeys.contains(sha(chain[i].publicKey().toDer()))) {
                badCerts.insert(chain[i].toDer()); positions.append(int(i));
                if (i == 2 && path.contains("rollover")) rollover = true;
            }
        }
        require(!badCerts.isEmpty(), "fixture has no compromised key");
        const auto names = chain[0].subjectAlternativeNames().values(QSsl::DnsEntry);
        require(!names.isEmpty() && !names[0].startsWith('*'), "explicit fixture hostname required");
        const auto errors = QSslCertificate::verify(chain, names[0]);
        int blacklisted = 0;
        for (const auto &error : errors) {
            require(error.error() != QSslError::HostNameMismatch && error.error() != QSslError::CertificateExpired
                && error.error() != QSslError::CertificateNotYetValid && error.error() != QSslError::NoSslSupport,
                "unrelated error cannot qualify chain rejection");
            if (error.error() == QSslError::CertificateBlacklisted) {
                ++blacklisted; actualBadCerts.insert(error.certificate().toDer());
            }
        }
        require(actualBadCerts == badCerts && blacklisted == badCerts.size(), "whole-chain blacklist missing or duplicated");
        chains.append(QJsonObject{{"fixture", QDir(root + "/chains").relativeFilePath(path)},
            {"hostname", names[0]}, {"compromised_positions", positions}, {"errors", errorsJson(errors)}});
    }
    require(chains.size() == 16 && rollover, "sixteen chains including rollover required");
    return {{"keys", keyChecks}, {"chains", chains}, {"healthy_roots", rootChecks},
        {"scope", "Supplied-chain policy; no omitted/reconstructed-chain or live incident claim"}};
}
static QJsonObject handshake(const QStringList &args)
{
    // default, or fixture <CA file> <port> <hostname> <tls12|tls13|negative> <expected code>
    const bool ordinary = args[1] == "default";
    QSslSocket socket;
    QList<QSslError> errors;
    QObject::connect(&socket, &QSslSocket::sslErrors, [&errors](const QList<QSslError> &values) { errors.append(values); });
    socket.setPeerVerifyMode(QSslSocket::VerifyPeer);
    QJsonArray roots, systemRoots;
    for (const auto &cert : QSslConfiguration::defaultConfiguration().caCertificates()) roots.append(sha(cert.toDer()));
    for (const auto &cert : QSslConfiguration::systemCaCertificates()) systemRoots.append(sha(cert.toDer()));
    int expected = 0;
    QSsl::SslProtocol protocol = QSsl::SecureProtocols;
    if (!ordinary) {
        require(args.size() == 7, "fixture arguments invalid");
        auto config = socket.sslConfiguration();
        config.setCaCertificates(args[2] == "untrusted" ? QList<QSslCertificate>{} : QSslCertificate::fromData(bytes(args[2])));
        protocol = args[5] == "tls12" ? QSsl::TlsV1_2 : args[5] == "tls13" ? QSsl::TlsV1_3 : QSsl::SecureProtocols;
        config.setProtocol(protocol); socket.setSslConfiguration(config);
        socket.setPeerVerifyName(args[4]);
        require(args[6] == "positive" || args[6] == "hostname" || args[6] == "expired" || args[6] == "untrusted", "unknown expected result");
        expected = args[6] == "hostname" ? int(QSslError::HostNameMismatch) : args[6] == "expired" ? int(QSslError::CertificateExpired) : args[6] == "untrusted" ? -1 : 0;
    }
    socket.connectToHostEncrypted(ordinary ? "www.python.org" : "127.0.0.1", ordinary ? 443 : args[3].toUShort());
    const bool encrypted = socket.waitForEncrypted(20000);
    if (expected == 0) {
        require(encrypted && errors.isEmpty() && !socket.peerCertificate().isNull(), "authenticated handshake failed");
        if (!ordinary) require(socket.sessionProtocol() == protocol, "negotiated TLS differs");
        socket.write("GET / HTTP/1.0\r\nHost: www.python.org\r\n\r\n");
        socket.waitForBytesWritten(10000);
        QByteArray response;
        while (!response.contains("200 OK") && socket.waitForReadyRead(10000)) response += socket.readAll();
        require(response.contains("200 OK"), "authenticated HTTP response missing");
    } else {
        require(!encrypted && !errors.isEmpty(), "negative peer accepted");
        bool correct = false;
        for (const auto &error : errors) {
            const auto code = error.error();
            if (expected == -1) correct |= code == QSslError::CertificateUntrusted || code == QSslError::SelfSignedCertificateInChain
                || code == QSslError::UnableToGetIssuerCertificate || code == QSslError::UnableToGetLocalIssuerCertificate
                || code == QSslError::UnableToVerifyFirstCertificate;
            else correct |= int(code) == expected;
        }
        require(correct, "negative rejected for wrong reason");
    }
    QJsonObject result{{"encrypted", encrypted}, {"protocol", int(socket.sessionProtocol())}, {"errors", errorsJson(errors)},
        {"default_trust", ordinary}, {"peer_sha256", sha(socket.peerCertificate().toDer())}, {"result", "PASS"}};
    if (ordinary) {
        result["configuration_ca_fingerprints"] = roots;
        result["qt_system_ca_fingerprints"] = systemRoots;
    }
    socket.abort(); return result;
}
int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        const auto args = app.arguments();
        require(QString::fromLatin1(qVersion()) == "6.12.0" && QSysInfo::currentCpuArchitecture() == "x86_64", "native Qt identity differs");
        require(QSslSocket::setActiveBackend("schannel") && QSslSocket::supportsSsl()
            && QSslSocket::activeBackend() == "schannel", "native Schannel backend unavailable");
        require(args.size() >= 2, "mode required");
        QJsonObject result = args[1] == "policy" ? policy(args.value(2)) : handshake(args);
        result["backend"] = QSslSocket::activeBackend(); result["qt"] = qVersion();
        result["runtime_library"] = QSslSocket::sslLibraryVersionString();
        result["loaded_modules"] = loadedModules();
        QTextStream(stdout) << QJsonDocument(result).toJson(QJsonDocument::Compact) << Qt::endl;
        return 0;
    } catch (const std::exception &error) {
        QTextStream(stderr) << error.what() << Qt::endl;
        return 1;
    }
}
