"""Run once: python -m backend.scripts.generate_cert"""
import os
import socket
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone
from backend.config import settings


def _get_lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def generate_self_signed_cert():
    lan_ip = _get_lan_ip()

    os.makedirs(os.path.dirname(settings.cert_file), exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, lan_ip or "localhost"),
    ])

    # SANs: always include localhost; add LAN IP when available
    sans: list[x509.GeneralName] = [x509.DNSName("localhost")]
    if lan_ip:
        sans.append(x509.IPAddress(ipaddress.IPv4Address(lan_ip)))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(settings.cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(settings.key_file, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))
    print(f"Cert written to {settings.cert_file}")
    print(f"Key written to {settings.key_file}")
    if lan_ip:
        print(f"Certificate covers LAN IP: {lan_ip}")
        print(f"Access ServerDash at: https://{lan_ip}:{settings.port}")

if __name__ == "__main__":
    generate_self_signed_cert()
