#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
企业微信消息加解密库
基于企业微信官方提供的加解密算法
"""

import base64
import hashlib
import random
import string
import struct
from Crypto.Cipher import AES

class FormatException(Exception):
    pass

class WXBizMsgCrypt:
    def __init__(self, sToken, sEncodingAESKey, sReceiveId):
        try:
            self.key = base64.b64decode(sEncodingAESKey + "=")
            assert len(self.key) == 32
        except Exception:
            raise FormatException("不合法的EncodingAESKey")
        self.token = sToken
        self.receiveid = sReceiveId

    def _get_sha1(self, token, timestamp, nonce, encrypt):
        """用SHA1算法生成安全签名"""
        try:
            sortlist = [token, timestamp, nonce, encrypt]
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode())
            return 0, sha.hexdigest()
        except Exception as e:
            return -40003, None

    def _get_signature(self, timestamp, nonce, encrypt):
        return self._get_sha1(self.token, timestamp, nonce, encrypt)

    def VerifyURL(self, sMsgSignature, sTimeStamp, sNonce, sEchoStr):
        """验证URL"""
        ret, signature = self._get_signature(sTimeStamp, sNonce, sEchoStr)
        if ret != 0:
            return ret, None
        if signature != sMsgSignature:
            return -40001, None
        ret, sReplyEchoStr = self._decrypt(sEchoStr)
        return ret, sReplyEchoStr

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        """解密消息"""
        import xml.etree.ElementTree as ET
        try:
            xml_tree = ET.fromstring(sPostData)
            encrypt = xml_tree.find("Encrypt").text
        except Exception:
            return -40002, None
        
        ret, signature = self._get_signature(sTimeStamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        if signature != sMsgSignature:
            return -40001, None
        ret, xml_content = self._decrypt(encrypt)
        return ret, xml_content

    def _decrypt(self, text):
        """解密"""
        try:
            cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            plain_text = cryptor.decrypt(base64.b64decode(text))
        except Exception:
            return -40007, None
        
        try:
            pad = plain_text[-1]
            if isinstance(pad, str):
                pad = ord(pad)
            content = plain_text[16:-pad]
            xml_len = struct.unpack("!I", content[:4])[0]
            xml_content = content[4:xml_len+4]
            from_receiveid = content[xml_len+4:].decode('utf-8')
        except Exception:
            return -40008, None
        
        if from_receiveid != self.receiveid:
            return -40005, None
        return 0, xml_content

    def EncryptMsg(self, sReplyMsg, sNonce, timestamp=None):
        """加密消息"""
        if timestamp is None:
            import time
            timestamp = str(int(time.time()))
        
        ret, encrypt = self._encrypt(sReplyMsg)
        if ret != 0:
            return ret, None
        
        ret, signature = self._get_signature(timestamp, sNonce, encrypt)
        if ret != 0:
            return ret, None
        
        xmlParse = """<xml>
<Encrypt><![CDATA[{0}]]></Encrypt>
<MsgSignature><![CDATA[{1}]]></MsgSignature>
<TimeStamp>{2}</TimeStamp>
<Nonce><![CDATA[{3}]]></Nonce>
</xml>"""
        return 0, xmlParse.format(encrypt, signature, timestamp, sNonce)

    def _encrypt(self, text):
        """加密"""
        text = text.encode('utf-8')
        text_length = struct.pack("!I", len(text))
        random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16)).encode()
        text = random_str + text_length + text + self.receiveid.encode('utf-8')
        
        # PKCS7 padding
        text_length = len(text)
        amount_to_pad = AES.block_size - (text_length % AES.block_size)
        if amount_to_pad == 0:
            amount_to_pad = AES.block_size
        pad = chr(amount_to_pad).encode()
        text = text + pad * amount_to_pad
        
        cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        try:
            ciphertext = cryptor.encrypt(text)
            return 0, base64.b64encode(ciphertext).decode('utf-8')
        except Exception:
            return -40006, None
