from logging import Logger
from hashlib import sha256

from cryptography.fernet import Fernet

from kvm_2_gcp.logger import get_logger


class Cipher:
    def __init__(self, logger: Logger = None):
        """Create a cipher object for encryption/decryption

        Args:
            logger (Logger): logger object
        """
        self.log = logger or get_logger('kvm-2-gcp')

    @property
    def __xork(self) -> bytes:
        """XOR key for encryption/decryption of the cipher key

        Returns:
            bytes: XOR key
        """
        return b'QboGBUxnhsP-FgScR-BEeRO4rCuGYU0P9rIzaWeO6kM='

    @property
    def key_file(self):
        """File path to store the cipher key

        Returns:
            str: file path to cipher key
        """
        return '/k2g/.env/.xork'

    def _create_key(self) -> bool:
        """Generate a cipher key for encryption/decryption

        Returns:
            bool: True if key was created successfully, False otherwise
        """
        try:
            with open(self.key_file, 'wb') as key_file:
                key_file.write(self.encrypt(Fernet.generate_key(), self.__xork))
            return True
        except Exception:
            self.log.exception('Failed to create key file')
            return False

    def load_key(self) -> bytes:
        """Load the cipher key from file and decrypt it using XOR key

        Returns:
            bytes: cipher key
        """
        try:
            with open(self.key_file, 'rb') as key_file:
                return self.decrypt(key_file.read(), self.__xork)
        except Exception:
            self.log.exception('Failed to load key file')
            return b''

    def passwd_xor(self, data: bytes, passwd: str) -> bytes:
        """Encrypt/Decrypt data using password. Password is hashed using sha256 and extended to the length of data

        Args:
            data (bytes): data to encrypt/decrypt
            passwd (str): password to encrypt/decrypt data

        Returns:
            bytes: encrypted/decrypted data
        """
        try:
            key = sha256(passwd.encode()).digest()
            extended_key = (key * (len(data) // len(key) + 1))[:len(data)]
            return bytes([b ^ extended_key[i % len(extended_key)] for i, b in enumerate(data)])
        except Exception:
            self.log.exception('Failed to encrypt/decrypt data')
        return b''

    @staticmethod
    def encrypt(data: bytes, key: bytes) -> bytes:
        """Encrypt data using Fernet

        Args:
            data (bytes): data to encrypt
            key (bytes): key to encrypt data with

        Returns:
            bytes: encrypted data
        """
        return Fernet(key).encrypt(data)

    @staticmethod
    def decrypt(data: bytes, key: bytes) -> bytes:
        """Decrypt data using Fernet

        Args:
            data (bytes): data to decrypt
            key (bytes): key to decrypt data with

        Returns:
            bytes: decrypted data
        """
        return Fernet(key).decrypt(data)
