"""
Audit test suite verifying multi-pass PII scrubbing and whitelist preservation.
"""
from review_pulsator.scrubber import PIIScrubber


def test_email_scrubbing():
    scrubber = PIIScrubber()
    text = "Contact support at john.doe@gmail.com immediately."
    scrubbed = scrubber.scrub(text)
    assert "john.doe@gmail.com" not in scrubbed
    assert "[ANONYMIZED_EMAIL]" in scrubbed
    assert "Contact support at" in scrubbed


def test_obfuscated_email_scrubbing():
    scrubber = PIIScrubber()
    text = "My email is alice . smith @ yahoo . com please reply."
    scrubbed = scrubber.scrub(text)
    assert "alice . smith @ yahoo . com" not in scrubbed
    assert "[ANONYMIZED_EMAIL]" in scrubbed
    assert "please reply" in scrubbed


def test_phone_scrubbing():
    scrubber = PIIScrubber()
    text = "Call me at +1 (555) 123-4567 to resolve the crash."
    scrubbed = scrubber.scrub(text)
    assert "555" not in scrubbed
    assert "[ANONYMIZED_PHONE]" in scrubbed
    assert "to resolve the crash" in scrubbed


def test_device_uuid_and_ip_scrubbing():
    scrubber = PIIScrubber()
    text = "Device 550e8400-e29b-41d4-a716-446655440000 on IP 192.168.1.101 failed auth."
    scrubbed = scrubber.scrub(text)
    assert "550e8400" not in scrubbed
    assert "192.168.1.101" not in scrubbed
    assert "[ANONYMIZED_DEVICE]" in scrubbed
    assert "failed auth" in scrubbed


def test_username_scrubbing():
    scrubber = PIIScrubber()
    text = "Hey @tech_guru99 the KYC verification step hangs."
    scrubbed = scrubber.scrub(text)
    assert "@tech_guru99" not in scrubbed
    assert "[ANONYMIZED_USER]" in scrubbed
    assert "the KYC verification step hangs" in scrubbed


def test_whitelist_preservation():
    scrubber = PIIScrubber()
    text = "Running on iOS with app v3.14.1 and got Error 404 during login."
    scrubbed = scrubber.scrub(text)
    assert "iOS" in scrubbed
    assert "v3.14.1" in scrubbed
    assert "Error 404" in scrubbed
    assert "[ANONYMIZED_" not in scrubbed


def test_html_unescaping():
    scrubber = PIIScrubber()
    text = "App crashes &lt;b&gt;constantly&lt;/b&gt; since update!"
    scrubbed = scrubber.scrub(text)
    assert "App crashes constantly since update!" in scrubbed
    assert "<b>" not in scrubbed
