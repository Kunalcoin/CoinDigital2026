"""
DDEX feed configuration for stores (Spotify, TikTok, etc.).
We always use ERN 4.3 for deployment (latest version).
Aligns with Sonosuite/Dream Entertainment sample (ERN 4.3).
"""
import os

# Coin Digital Party ID (DDEX) - use without hyphens in XML
COIN_DIGITAL_PARTY_ID = os.getenv("DDEX_PARTY_ID_COIN", "PADPIDA2023031502Y")
COIN_DIGITAL_PARTY_NAME = os.getenv("DDEX_PARTY_NAME_COIN", "Coin Digital")

# Store recipients (ERN 4.3)
SPOTIFY_PARTY_ID = "PADPIDA2011072101T"
SPOTIFY_PARTY_NAME = "Spotify"

# TikTok / ByteDance (ERN 4.3; Party ID from TikTok Music Delivery Specs)
TIKTOK_PARTY_ID = "PADPIDA2018082301A"
TIKTOK_PARTY_NAME = "TikTok / Bytedance"

# Audiomack (ERN 4.3) - from Audiomack onboard DDEX samples; override via env if needed
AUDIOMACK_PARTY_ID = os.getenv("DDEX_PARTY_ID_AUDIOMACK", "PADPIDA2017103008S")
AUDIOMACK_PARTY_NAME = os.getenv("DDEX_PARTY_NAME_AUDIOMACK", "Audiomack LLC")

# Meta (Facebook / Instagram Music) – ERN 4.3 sample: two recipients required
META_FACEBOOK_SRP_PARTY_ID = os.getenv("DDEX_PARTY_ID_META_SRP", "PADPIDA2013071501L")
META_FACEBOOK_SRP_PARTY_NAME = os.getenv("DDEX_PARTY_NAME_META_SRP", "Facebook_SRP")
META_FACEBOOK_AAP_PARTY_ID = os.getenv("DDEX_PARTY_ID_META_AAP", "PADPIDA2018010804X")
META_FACEBOOK_AAP_PARTY_NAME = os.getenv("DDEX_PARTY_NAME_META_AAP", "Facebook_AAP")

# Territory for all deals
DEFAULT_TERRITORY = "Worldwide"

# ERN version: we always use 4.3 for deployment
ERN_NAMESPACE = "http://ddex.net/xml/ern/43"
ERN_SCHEMA_LOCATION = "http://ddex.net/xml/ern/43 http://ddex.net/xml/ern/43/release-notification.xsd"
RELEASE_PROFILE = "Audio"
LANGUAGE_SCRIPT_CODE = "en"
AVS_VERSION = "6"

# Commercial models and use types (Spotify-style)
DEAL_SUBSCRIPTION = "SubscriptionModel"
DEAL_ADVERTISEMENT = "AdvertisementSupportedModel"
USE_CONDITIONAL_DOWNLOAD = "ConditionalDownload"
USE_ON_DEMAND_STREAM = "OnDemandStream"
USE_NON_INTERACTIVE_STREAM = "NonInteractiveStream"

# TikTok UGC / Library feed (ERN 4.3)
DEAL_RIGHTS_CLAIM_MODEL = "RightsClaimModel"
USE_USER_MAKE_AVAILABLE_USER_PROVIDED = "UserMakeAvailableUserProvided"
RIGHTS_CLAIM_POLICY_MONETIZE = "Monetize"
RIGHTS_CLAIM_POLICY_BLOCK_ACCESS = "BlockAccess"
RIGHTS_CONTROLLER_ROLE = "RightsController"

# Meta (Facebook/Instagram): RightsClaimModel + UserMakeAvailableUserProvided/LabelProvided + RightsClaimPolicy
USE_USER_MAKE_AVAILABLE_LABEL_PROVIDED = "UserMakeAvailableLabelProvided"
RIGHTS_CLAIM_POLICY_TYPE = "RightsClaimPolicyType"

# Download deal profile (ERN 4.3) — PayAsYouGoModel + PermanentDownload
DEAL_PAY_AS_YOU_GO = "PayAsYouGoModel"
USE_PERMANENT_DOWNLOAD = "PermanentDownload"
