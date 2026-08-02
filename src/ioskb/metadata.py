"""Conservative metadata extraction for Vectorize and full-text exports."""
import re
from pathlib import Path

_VERSION = re.compile(r"\b(iOS|iPadOS|macOS|tvOS|watchOS|Swift)\s*(\d+(?:\.\d+)*)\b", re.I)
_TOPICS = (
    (r"weak|side[_ -]?table|引用计数|autorelease", "内存管理"),
    (r"runloop|运行循环|source0|source1", "RunLoop"),
    (r"kvo|kvc", "KVC 与 KVO"),
    (r"objc_msgsend|runtime|消息转发|swizzling", "Objective-C Runtime"),
    (r"gcd|dispatch|actor|async|await|线程|并发", "并发"),
    (r"uikit|viewcontroller|autolayout|calayer|渲染", "UIKit 与渲染"),
    (r"urlsession|http|https|tcp|网络", "网络"),
    (r"dyld|mach-o|启动|链接|编译", "编译链接与启动"),
)
_LANGUAGES = {
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".h": "Objective-C/C",
    ".c": "C",
    ".cpp": "C++",
    ".s": "Assembly",
}


def export_metadata(path, title_path, text):
    """Return only labels directly visible in a source path or excerpt.

    Version fields are intentionally absent unless an explicit ``iOS 17`` or
    ``Swift 5.9`` style marker occurs in the source. This keeps the website
    from presenting inferred compatibility as fact.
    """
    value = f"{title_path}\n{text[:4000]}"
    lower = value.lower()
    metadata = {}
    ios_versions, swift_versions = [], []
    platforms = set()
    for family, version in _VERSION.findall(value):
        family = family.lower()
        if family == "swift":
            swift_versions.append(version)
        else:
            ios_versions.append(version)
            platforms.add(
                {"ios": "iOS", "ipados": "iPadOS", "macos": "macOS", "tvos": "tvOS", "watchos": "watchOS"}[family]
            )
    if ios_versions:
        metadata["ios_version"] = ", ".join(dict.fromkeys(ios_versions))
    if swift_versions:
        metadata["swift_version"] = ", ".join(dict.fromkeys(swift_versions))
    if platforms:
        metadata["platform"] = " / ".join(sorted(platforms))

    for pattern, topic in _TOPICS:
        if re.search(pattern, lower, re.I):
            metadata["topic"] = topic
            break
    section = [part.strip() for part in title_path.split("›") if part.strip()]
    if section:
        metadata["section"] = section[-1]
    language = _LANGUAGES.get(Path(path).suffix.lower())
    if language:
        metadata["language"] = language
    return metadata
