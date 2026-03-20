from django.db import models
from django.utils import timezone
from main.models import CDUser

# Constants for music-related models
LANGUAGES = [
    "Afrikaans", "Amharic", "Arabic", "Arabic - Egyptian", "Arabic - Moroccan", 
    "Armenian", "Assamese", "Azerbaijani", "Basque", "Belarusian", "Bengali", 
    "Bhojpuri", "Bosnian", "Bulgarian", "Cambodian", "Catalan", "Chechen", 
    "Chinese", "Chinese - Cantonese", "Chinese - Hakka", "Chinese - Mandarin", 
    "Croatian", "Czech", "Danish", "Dutch", "English", "Estonian", "Filipino", 
    "Finnish", "French", "Galician", "Georgian", "German", "Greek", "Gujarati", 
    "Haitian", "Haitian Creole", "Haryanvi", "Hawaiian", "Hebrew", "Hindi", 
    "Hungarian", "Icelandic", "Igbo", "Indonesian", "Irish", "Italian", 
    "Japanese", "Kannada", "Kazakh", "Konkani", "Korean", "Kurdish", "Lao", 
    "Latin", "Latvian", "Lingala", "Lithuanian", "Luganda", "Macedonian", 
    "Malay", "Malayalam", "Maori", "Marathi", "Mongolian", "Nepali", 
    "Norwegian", "Oriya", "Persian", "Polish", "Portuguese", "Punjabi", 
    "Rajasthani", "Romanian", "Russian", "Samoan", "Sanskrit", "Sepedi", 
    "Serbian", "Shona", "Slovak", "Slovene", "Sotho", "Spanish", "Swahili", 
    "Swedish", "Tagalog", "Tahitian", "Tamazight", "Tamil", "Telugu", "Thai", 
    "Tsonga", "Tswana", "Turkish", "Twi", "Ukrainian", "Urdu", "Venda", 
    "Vietnamese", "Xhosa", "Zulu"
]

GENRES = [
    "Alternative", "Alternative/Experimental", "Alternative/Gothic", "Alternative/Grunge",
    "Alternative/Indie Pop", "Alternative/Indie Rock", "Alternative/Rock", "Ambient/New Age",
    "Ambient/New Age/Meditation", "Blues", "Blues/Contemporary Blues", "Blues/New Orleans Blues",
    "Blues/Traditional Blues", "Children's Music", "Children's Music/Classic", "Children's Music/Holiday",
    "Children's Music/Stories", "Classical", "Classical/Antique", "Classical/Baroque",
    "Classical/Chamber", "Classical/Concert", "Classical/Modern Compositions", "Classical/Opera",
    "Classical/Orchestral", "Classical/Piano", "Classical/Romantic", "Comedy", "Country",
    "Country/Bluegrass", "Country/Contemporary", "Country/Honky Tonk", "Country/Nashville",
    "Country/Pop", "Country/Square Dance", "Easy Listening", "Easy Listening/Bar Jazz/Cocktail",
    "Easy Listening/Bossa Nova", "Easy Listening/Lounge", "Easy Listening/Traditional",
    "Electronic", "Electronic/Acid House", "Electronic/Breaks", "Electronic/Broken beat",
    "Electronic/Chill Out", "Electronic/DJ Tools/Sample Packs", "Electronic/Dance",
    "Electronic/Deep House", "Electronic/Downtempo - experimental", "Electronic/Drum & Bass",
    "Electronic/Dub/Reggae/Dancehall", "Electronic/Dubstep/Grime", "Electronic/Electro House",
    "Electronic/Glitch Hop", "Electronic/Hard Dance", "Electronic/Hard Techno",
    "Electronic/Hardcore", "Electronic/Hardstyle", "Electronic/House",
    "Electronic/Indie Dance/Nu Disco", "Electronic/Jazz", "Electronic/Minimal",
    "Electronic/Pop Trance", "Electronic/Progressive House", "Electronic/Psy-Trance",
    "Electronic/Tech House", "Electronic/Techno", "Electronic/Trance", "Electronic/Trip Hop",
    "Experimental", "Fitness&Workout", "Flamenco", "Folk", "Funk/R&B", "Hip-Hop/Rap",
    "Hip-Hop/Rap/Gangsta & Hardcore", "Holiday/Christmas", "Inspirational", "Jazz",
    "Jazz/Bebop", "Jazz/Big Band", "Jazz/Brazilian Jazz", "Jazz/Classic", "Jazz/Contemporary",
    "Jazz/Dixie/Rag Time", "Jazz/Free Jazz", "Jazz/Fusion", "Jazz/Jazz Funk",
    "Jazz/Latin Jazz", "Jazz/Nu Jazz/Acid Jazz", "Jazz/Smooth Jazz", "Jazz/Swing",
    "Jazz/Traditional", "Jazz/World", "Karaoke", "Latin", "Latin/Bachata", "Latin/Banda",
    "Latin/Big Band", "Latin/Bolero", "Latin/Bossa Nova", "Latin/Brasil/Tropical",
    "Latin/Christian", "Latin/Conjunto", "Latin/Corridos", "Latin/Cuban", "Latin/Cumbia",
    "Latin/Duranguense", "Latin/Electronica", "Latin/Grupero", "Latin/Hip Hop",
    "Latin/Latin Rap", "Latin/Mambo", "Latin/Mariachi", "Latin/Norteño", "Latin/Pop",
    "Latin/Ranchera", "Latin/Reggaeton", "Latin/Regional Mexicano", "Latin/Rock en Español",
    "Latin/Salsa", "Latin/Salsa/Merengue", "Latin/Sierreño", "Latin/Sonidero",
    "Latin/Tango", "Latin/Tejano", "Latin/Tierra Caliente", "Latin/Traditional Mexican",
    "Latin/Vallenato", "New Age", "Pop", "Pop/Contemporary/Adult", "Pop/J-Pop", "Pop/K-Pop",
    "Pop/Mandopop", "Pop/Singer Songwriter", "Punk", "R&B", "Reggae", "Rock",
    "Rock/Black Metal", "Rock/Blues-Rock", "Rock/Brit-Pop", "Rock/British Invasion",
    "Rock/Chinese Rock", "Rock/Classic", "Rock/Death Metal", "Rock/Glam Rock",
    "Rock/Hair Metal", "Rock/Hard Rock", "Rock/Heavy Metal", "Rock/Jam Bands",
    "Rock/Korean Rock", "Rock/Progressive", "Rock/Psychedelic", "Rock/Rock 'n' Roll",
    "Rock/Rockabilly", "Rock/Russian Rock", "Rock/Singer/Songwriter", "Rock/Southern Rock",
    "Rock/Surf", "Rock/Tex-Mex", "Rock/Turkish Rock", "Ska", "Soul", "Soundtrack",
    "Soundtrack/Anime", "Soundtrack/Musical", "Soundtrack/TV", "Spiritual",
    "Spiritual/Christian", "Spiritual/Gospel", "Spiritual/Gregorian", "Spiritual/India",
    "Spiritual/Judaica", "Spiritual/World", "Spoken Word/Speeches", "Trap",
    "Trap/Future Bass", "Trap/Future Bass/Twerk", "Vocal/Nostalgia", "World",
    "World/African", "World/African/African Dancehall", "World/African/African Reggae",
    "World/African/Afrikaans", "World/African/Afro-Beat", "World/African/Afro-Folk",
    "World/African/Afro-Fusion", "World/African/Afro-House", "World/African/Afro-Pop",
    "World/African/Afro-Soul", "World/African/Afrobeats", "World/African/Alte",
    "World/African/Amapiano", "World/African/Benga", "World/African/Bongo-Flava",
    "World/African/Coupé-Décalé", "World/African/Gqom", "World/African/Highlife",
    "World/African/Kizomba", "World/African/Kuduro", "World/African/Kwaito",
    "World/African/Maskandi", "World/African/Mbalax", "World/African/Ndombolo",
    "World/African/Shangaan Electro", "World/African/Soukous", "World/African/Taarab",
    "World/African/Zouglou", "World/Afro-Beat", "World/Afro-Pop", "World/Americas/Argentina",
    "World/Americas/Brazilian", "World/Americas/Brazilian/Axé", "World/Americas/Brazilian/Baile Funk",
    "World/Americas/Brazilian/Black Music", "World/Americas/Brazilian/Bossa Nova",
    "World/Americas/Brazilian/Chorinho", "World/Americas/Brazilian/Folk",
    "World/Americas/Brazilian/Forró", "World/Americas/Brazilian/Frevo",
    "World/Americas/Brazilian/Funk Carioca", "World/Americas/Brazilian/MPB",
    "World/Americas/Brazilian/Marchinha", "World/Americas/Brazilian/Pagode",
    "World/Americas/Brazilian/Samba", "World/Americas/Brazilian/Samba-Rock",
    "World/Americas/Brazilian/Samba-de-Raiz", "World/Americas/Brazilian/Samba-enredo",
    "World/Americas/Brazilian/Sambalanço", "World/Americas/Brazilian/Sertanejo",
    "World/Americas/Cajun-Creole", "World/Americas/Calypso", "World/Americas/Colombia",
    "World/Americas/Cuba-Caribbean", "World/Americas/Mexican", "World/Americas/North-American",
    "World/Americas/Panama", "World/Americas/Peru", "World/Americas/South-American",
    "World/Arabic", "World/Asian/Central Asia", "World/Asian/China", "World/Asian/Indian",
    "World/Asian/Indian/Assamese", "World/Asian/Indian/Bengali", "World/Asian/Indian/Bengali/Rabindra Sangeet",
    "World/Asian/Indian/Bhojpuri", "World/Asian/Indian/Bollywood", "World/Asian/Indian/Carnatic Classical",
    "World/Asian/Indian/Devotional & Spiritual", "World/Asian/Indian/Ghazals",
    "World/Asian/Indian/Gujarati", "World/Asian/Indian/Haryanvi", "World/Asian/Indian/Hindustani Classical",
    "World/Asian/Indian/Indian Classical", "World/Asian/Indian/Indian Folk", "World/Asian/Indian/Indian Pop",
    "World/Asian/Indian/Kannada", "World/Asian/Indian/Malayalam", "World/Asian/Indian/Marathi",
    "World/Asian/Indian/Odia", "World/Asian/Indian/Punjabi", "World/Asian/Indian/Punjabi/Punjabi Pop",
    "World/Asian/Indian/Rajasthani", "World/Asian/Indian/Regional Indian", "World/Asian/Indian/Sufi",
    "World/Asian/Indian/Tamil", "World/Asian/Indian/Telugu", "World/Asian/Indian/Urdu",
    "World/Asian/Indian", "World/Asian/India-Bollywood", "World/Asian/Japan", "World/Asian/South Asia",
    "World/Australian/Pacific", "World/Ethnic", "World/Europe/Eastern", "World/Europe/French",
    "World/Europe/German", "World/Europe/Northern", "World/Europe/Southern", "World/Europe/Spain",
    "World/Europe/Western", "World/Mediterranean/Greece", "World/Mediterranean/Italy",
    "World/Mediterranean/Spain", "World/Russian", "World/Worldbeat"
]

ARTIST_ROLES = [
    "Accordion", "Actor", "Adapter", "Assistant Engineer", "Background Vocals", "Banjo", "Bass Guitar", "Bassoon",
    "Bells", "Cello", "Choir", "Clarinet", "Co-Producer", "Composer", "Conductor", "Drums", "Ensemble", "Featured Artist",
    "Fiddle", "Flute", "Graphic Design", "Guitar", "Harmonica", "Harp", "Horn", "Keyboards", "Lute", "Lyricist",
    "Mastering Engineer", "Metallophone", "Mixing Engineer", "Oboe", "Orchestra", "Organ", "Other Performer",
    "Percussion", "Performer", "Piano", "Primary Artist", "Producer", "Programming", "Rap",
    "Recording Engineer", "Recorder", "Remixer", "Saxophone", "Synthesizer", "Tambourine", "Trombone", "Trumpet",
    "Viola", "Viola de Gamba", "Violin", "Vocals", "Whistle", "with", "Xylophone"
]


# Models
class UniqueCode(models.Model):
    class TYPE(models.TextChoices):
        UPC = "upc", "UPC"
        ISRC = "isrc", "ISRC"

    type = models.CharField("Type", max_length=20, choices=TYPE.choices, null=False)
    code = models.CharField("Code", max_length=50, null=False, unique=True)
    assigned = models.BooleanField("Is Assigned", default=False, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Unique Code"
        verbose_name_plural = "Unique Codes"
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['assigned']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]


class Label(models.Model):
    user = models.ForeignKey(
        CDUser, on_delete=models.CASCADE, null=False, verbose_name="User"
    )
    label = models.CharField("Label", max_length=255, null=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = "Label"
        verbose_name_plural = "Labels"
        indexes = [
            models.Index(fields=['user']),
        ]


class Release(models.Model):
    # Static
    class ALBUM_FORMAT(models.TextChoices):
        SINGLE = "single", "Single"
        EP = "ep", "EP"
        ALBUM = "album", "Album"

    class PRICE_CATEGORY(models.TextChoices):
        MID = "mid", "Mid"
        BUDGET = "budget", "Budget"
        FULL = "full", "Full"
        PREMIUM = "premium", "Premium"

    class LICENSE_TYPE(models.TextChoices):
        COPYRIGHT = "copyright", "Copyright"
        CREATIVE_COMMON = "creative_common", "Creative Common"

    class APPLE_MUSIC_COMMERCIAL_MODEL(models.TextChoices):
        """Apple iTunes Importer cleared_for_sale / cleared_for_stream (Merlin Bridge checklist)."""
        BOTH = "both", "Streaming + download (default)"
        STREAMING_ONLY = "streaming_only", "Streaming only"
        RETAIL_ONLY = "retail_only", "Retail / download only (no streaming)"

    # Fields
    title = models.CharField("Title", max_length=255, null=False)
    cover_art_url = models.CharField("Cover Art", max_length=1024, default="")
    remix_version = models.CharField("Remix Version", max_length=255, default="")
    primary_genre = models.CharField(
        "Primary Genre",
        max_length=512,
        choices=[(genre, genre) for genre in GENRES],
        null=False,
        default=GENRES[0],
    )
    secondary_genre = models.CharField(
        "Secondary Genre",
        max_length=512,
        choices=[(genre, genre) for genre in GENRES],
        default=""
    )
    language = models.CharField(
        "Language",
        max_length=512,
        choices=[(language, language) for language in LANGUAGES],
        null=False,
        default=LANGUAGES[0],
    )
    album_format = models.CharField(
        "Album Format",
        max_length=20,
        choices=ALBUM_FORMAT.choices,
        null=False,
        default=ALBUM_FORMAT.SINGLE,
    )
    upc = models.CharField("UPC", max_length=50, default="")
    reference_number = models.CharField("Reference Number", max_length=255, default="")
    grid = models.CharField("GRID", max_length=255, default="")
    description = models.TextField("Description", default="",max_length=1024)
    created_by = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="Created by"
    )
    published = models.BooleanField("Is Published", default=False)
    takedown_requested = models.BooleanField("Is Takedown Requested", default=False)
    published_at = models.DateTimeField("Published At", null=True)
    approval_status = models.CharField(
        "Approval Status",
        max_length=50,
        default="pending",
        blank=True,
    )
    submitted_for_approval_at = models.DateTimeField(
        "Submitted for approval at",
        null=True,
        blank=True,
        help_text="When the release was submitted for distribution approval.",
    )
    # Sonosuite API delivery (operation IDs returned by Sonosuite)
    sonosuite_operation_ids = models.TextField("Sonosuite operation IDs", blank=True, default="")
    # License fields
    price_category = models.CharField(
        "Price Category",
        max_length=100,
        choices=PRICE_CATEGORY.choices,
        default=PRICE_CATEGORY.BUDGET,
    )
    digital_release_date = models.DateField("Digital Release Date", null=True)
    original_release_date = models.DateField("Original Release Date", null=True)
    license_type = models.CharField(
        "License Type",
        max_length=50,
        choices=LICENSE_TYPE.choices,
        default=LICENSE_TYPE.COPYRIGHT,
    )
    license_holder_year = models.CharField("License Holder Year", max_length=4, default="")
    license_holder_name = models.CharField("License Holder Name", max_length=255, default="")
    copyright_recording_year = models.CharField(
        "Copyright Recording Year", max_length=255, default=""
    )
    copyright_recording_text = models.CharField(
        "Copyright Recording Text", max_length=255, default=""
    )
    territories = models.CharField(
        "Territories", max_length=255, default="Entire World"
    )
    apple_music_commercial_model = models.CharField(
        "Apple Music commercial model",
        max_length=20,
        choices=APPLE_MUSIC_COMMERCIAL_MODEL.choices,
        default=APPLE_MUSIC_COMMERCIAL_MODEL.BOTH,
        help_text="Merlin Bridge: use Streaming only or Retail only for checklist test deliveries; default is both.",
    )
    apple_music_preorder_start_date = models.DateField(
        "Apple Music pre-order sales start date",
        null=True,
        blank=True,
        help_text="If set, metadata.xml includes preorder_sales_start_date on each product (Merlin preorder checklist). "
        "Must be before Digital release date (street/sale date) and typically in the future when you deliver.",
    )
    label = models.ForeignKey(
        Label, on_delete=models.DO_NOTHING, verbose_name="Label", null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Release"
        verbose_name_plural = "Releases"
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['upc']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['grid']),
            models.Index(fields=['language']),
            models.Index(fields=['created_by']),
            models.Index(fields=['updated_at']),
            # Analytics optimization indexes
            models.Index(fields=['published']),
            models.Index(fields=['published_at']),
            models.Index(fields=['primary_genre']),
            models.Index(fields=['album_format']),
            models.Index(fields=['digital_release_date']),
            models.Index(fields=['created_by', 'published']),
            models.Index(fields=['label', 'created_by']),
        ]


class DistributionJob(models.Model):
    class ACTION(models.TextChoices):
        DISTRIBUTE = "distribute", "Distribute to stores"
        TAKEDOWN = "takedown", "Takedown from stores"

    class STATUS(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="distribution_jobs")
    requested_by = models.ForeignKey(CDUser, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION.choices)
    status = models.CharField(max_length=20, choices=STATUS.choices, default=STATUS.QUEUED)
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(default=0)
    store_results = models.JSONField(default=dict, blank=True)
    message = models.TextField(default="", blank=True)

    class Meta:
        verbose_name = "Distribution Job"
        verbose_name_plural = "Distribution Jobs"
        indexes = [
            models.Index(fields=["release", "requested_at"]),
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["action", "requested_at"]),
        ]


class Track(models.Model):
    # Static
    class EXPLICIT_LYRICS(models.TextChoices):
        NOT_EXPLICIT = "not_explicit", "Not Explicit"
        EXPLICIT = "explicit", "Explicit"
        CLEANED = "cleaned", "Cleaned"

    # Fields
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, null=False, verbose_name="Release"
    )
    remix_version = models.CharField("Remix Version", max_length=255)
    title = models.CharField("Title", max_length=1024, null=False)
    created_by = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="Created by"
    )
    audio_track_url = models.CharField("Audio Track", max_length=1024, blank=True, default="")
    audio_wav_url = models.CharField("Audio WAV", max_length=1024, blank=True, default="")
    audio_mp3_url = models.CharField("Audio MP3", max_length=1024, blank=True, default="")
    audio_flac_url = models.CharField("Audio FLAC", max_length=1024, blank=True, default="")
    audio_uploaded_at = models.DateTimeField(
        "Audio uploaded at (UTC)",
        null=True,
        blank=True,
        help_text="When the WAV was uploaded (stored UTC; display in IST).",
    )
    primary_genre = models.CharField(
        "Primary Genre", max_length=512, choices=[(genre, genre) for genre in GENRES]
    )
    secondary_genre = models.CharField(
        "Secondary Genre", max_length=512, choices=[(genre, genre) for genre in GENRES], default="", null=True
    )
    isrc = models.CharField("ISRC", max_length=255)
    iswc = models.CharField("ISWC", max_length=255, default="")
    publishing_rights_owner = models.CharField(
        "Publishing Rights Owner", max_length=255, default=""
    )
    publishing_rights_year = models.CharField("Publishing Rights Year", max_length=4, default="")
    lyrics = models.TextField("Lyrics", max_length=4096, null=True)
    explicit_lyrics = models.CharField(
        "Explicit Lyrics",
        max_length=20,
        choices=EXPLICIT_LYRICS.choices,
        default=EXPLICIT_LYRICS.NOT_EXPLICIT,
        null=False,
    )
    language = models.CharField(
        "Language",
        max_length=255,
        choices=[(language, language) for language in LANGUAGES],
        null=False,
    )
    available_separately = models.BooleanField("Is Available Separately", default=False)
    start_point = models.CharField("Start Point", max_length=10)
    notes = models.TextField("Notes",max_length=1024)
    sequence = models.PositiveIntegerField(
        "Display order",
        default=0,
        help_text="Order of track in release (1-based). 0 = legacy, use id order.",
    )
    apple_music_instant_grat = models.BooleanField(
        "Apple Music instant gratification (pre-order)",
        default=False,
        help_text="During an Apple Music pre-order, mark tracks that are instant gratification. "
        "Deliveries emit <preorder_type>instant-gratification</preorder_type> on those tracks and "
        "<preorder_type>standard</preorder_type> on others (track-level, not inside <product>). "
        "At most half the tracks may be IG.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
        

    class Meta:
        verbose_name = "Track"
        verbose_name_plural = "Tracks"
        indexes = [
            models.Index(fields=['isrc']),
            models.Index(fields=['primary_genre']),
            models.Index(fields=['secondary_genre']),
            models.Index(fields=['language']),
            models.Index(fields=['created_by']),
            models.Index(fields=['updated_at']),
            # Analytics optimization indexes
            models.Index(fields=['release']),
            models.Index(fields=['release', 'created_by']),
        ]

class Artist(models.Model):
    user = models.ForeignKey(
        CDUser, on_delete=models.DO_NOTHING, null=False, verbose_name="User"
    )
    artist_id = models.IntegerField("Artist ID", null=True, blank=True) # Same ID as artists table
    name = models.CharField("Full Name", max_length=255)
    first_name = models.CharField("First Name", max_length=100, default="")
    last_name = models.CharField("Last Name", max_length=100, default="")
    apple_music_id = models.CharField("Apple Music ID", max_length=1024, default="")
    spotify_id = models.CharField("Spotify ID", max_length=1024, default="")
    youtube_username = models.CharField("Youtube Username", max_length=1024, default="")
    audiomack_id = models.CharField("Audiomack Artist ID", max_length=1024, default="", blank=True)
    soundcloud_page = models.CharField("Soundcloud Page", max_length=1024, default="")
    facebook_page = models.CharField("Facebook Page", max_length=1024, default="")
    x_username = models.CharField("X Username", max_length=1024, default="")
    website = models.CharField("Website", max_length=1024, default="")
    biography = models.CharField("Biography", max_length=1024, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Artist"
        verbose_name_plural = "Artists"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['name']),
        ]


class RelatedArtists(models.Model):
    release = models.ForeignKey(
        Release,
        on_delete=models.DO_NOTHING,
        related_name="release_artists",
        null=True,
        verbose_name="Release",
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.DO_NOTHING,
        related_name="track_artists",
        verbose_name="Track",
        null=True,
    )
    relation_key = models.CharField(
        "Relation Key",
        max_length=30,
        choices=[("release", "release"), ("track", "track")],
    )
    artist = models.ForeignKey(
        Artist,
        on_delete=models.DO_NOTHING,
        related_name="related_records",
        verbose_name="Artist",
    )
    role = models.CharField(
        "Role",
        choices=[(role, role) for role in ARTIST_ROLES],
        max_length=250,
        null=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role} | {self.artist.name}"

    class Meta:
        verbose_name = "Related Artist"
        verbose_name_plural = "Related Artists"
        indexes = [
            models.Index(fields=['relation_key']),
            models.Index(fields=['role']),
            # Analytics optimization indexes
            models.Index(fields=['artist']),
            models.Index(fields=['release']),
            models.Index(fields=['track']),
            models.Index(fields=['track', 'artist']),
            models.Index(fields=['release', 'artist']),
        ]


class Metadata(models.Model):
    """
    Metadata model for track information essential for royalties
    """
    isrc = models.CharField("ISRC", max_length=50, primary_key=True)
    release = models.CharField("Release", max_length=2000)
    display_artist = models.CharField("Display Artist", max_length=200, null=True, blank=True)
    release_launch = models.DateTimeField("Release Launch", null=True, blank=True)
    user = models.CharField("User", max_length=200)  # Username/email reference
    label_name = models.CharField("Label Name", max_length=200, null=True, blank=True)
    primary_genre = models.CharField("Primary Genre", max_length=200, null=True, blank=True)
    secondary_genre = models.CharField("Secondary Genre", max_length=200, null=True, blank=True)
    track_no = models.IntegerField("Track Number", null=True, blank=True)
    track = models.CharField("Track", max_length=2000)
    track_display_artist = models.CharField("Track Display Artist", max_length=200, null=True, blank=True)
    track_primary_genre = models.CharField("Track Primary Genre", max_length=200, null=True, blank=True)
    upc = models.CharField("UPC", max_length=200, null=True, blank=True)

    class Meta:
        verbose_name = "Metadata"
        verbose_name_plural = "Metadata"
        indexes = [
            models.Index(fields=['isrc'], name='ISRC_metadata'),
            models.Index(fields=['user'], name='users_metadata'),
            models.Index(fields=['upc'], name='upc_metadata'),
            # Analytics optimization indexes
            models.Index(fields=['release_launch']),
            models.Index(fields=['label_name']),
            models.Index(fields=['primary_genre']),
            models.Index(fields=['track_display_artist']),
            models.Index(fields=['user', 'isrc']),
            models.Index(fields=['user', 'primary_genre']),
        ]

    def __str__(self):
        return f"{self.isrc} - {self.track}"


class Royalties(models.Model):
    royalty_id = models.AutoField("Royalty ID", primary_key=True, unique=True)
    start_date = models.DateField("Start Date")
    end_date = models.DateField("End Date")
    country = models.CharField("Country",max_length=255)
    currency = models.CharField("Currency",max_length=255)
    type = models.CharField("Type",max_length=255)
    units = models.BigIntegerField("Units")
    unit_price = models.FloatField("Unit Price")
    gross_total = models.FloatField("Gross Total")
    channel_costs = models.FloatField("Channel Costs")
    taxes = models.FloatField("Taxes")
    net_total = models.FloatField("Net Total")
    currency_rate = models.FloatField("Currency Rate")
    net_total_INR = models.FloatField("Net Total INR")
    channel = models.CharField("Channel",max_length=255)
    isrc = models.CharField("ISRC", max_length=50)
    gross_total_INR = models.FloatField("Gross Total INR")
    other_costs_INR = models.FloatField("Other Costs INR")
    channel_costs_INR = models.FloatField("Channel Costs INR")
    taxes_INR = models.FloatField("Taxes INR")
    gross_total_client_currency = models.FloatField("Gross Total Client Currency")
    other_costs_client_currency = models.FloatField("Other Costs Client Currency")
    channel_costs_client_currency = models.FloatField("Channel Costs Client Currency")
    taxes_client_currency = models.FloatField("Taxes Client Currency")
    net_total_client_currency = models.FloatField("Net Total Client Currency")
    confirmed_date = models.DateField("Confirmed Date")

    class Meta:
        verbose_name = "Royalty"
        verbose_name_plural = "Royalties"
        indexes = [
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["gross_total_INR"]),
            models.Index(fields=["net_total"]),
            models.Index(fields=["net_total_INR"]),
            models.Index(fields=["confirmed_date"]),
            models.Index(fields=["isrc"]),
            models.Index(fields=["end_date"]),
            models.Index(fields=["start_date"]),
            # Analytics optimization indexes
            models.Index(fields=["country"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["type"]),
            models.Index(fields=["isrc", "net_total_INR"]),
            models.Index(fields=["isrc", "net_total_INR", "confirmed_date"]),
        ]

    def __str__(self):
        return f"Royalty {self.royalty_id} - {self.isrc}"



class SplitReleaseRoyalty(models.Model):
    user_id = models.ForeignKey(
        CDUser, on_delete=models.CASCADE, related_name="split_release_royalties"
    )
    release_id = models.ForeignKey(
        Release, on_delete=models.CASCADE, related_name="split_release_royalties"
    )
    track_id = models.ForeignKey(
        Track, on_delete=models.CASCADE, related_name="split_release_royalties"
    )
    recipient_name = models.CharField("Recipient Name", max_length=255)
    recipient_email = models.EmailField("Recipient Email")
    recipient_role = models.CharField("Role", max_length=255, choices=[(role, role) for role in ARTIST_ROLES])
    recipient_percentage = models.FloatField("Percentage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Split Release Royalty"
        verbose_name_plural = "Split Release Royalties"
        constraints = [
        models.UniqueConstraint(
                fields=['user_id', 'recipient_email', 'release_id', 'track_id'],
                name='unique_user_release_track'
            )
        ]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["release_id"]),
            models.Index(fields=["track_id"]),
            models.Index(fields=["recipient_email"]),
            models.Index(fields=["recipient_name"]),
            models.Index(fields=["recipient_role"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
            # Analytics optimization indexes
            models.Index(fields=["recipient_percentage"]),
            models.Index(fields=["user_id", "track_id"]),
            models.Index(fields=["user_id", "release_id"]),
        ]

    def __str__(self):
        return f"SplitReleaseRoyalty: User {self.user_id}, Release {self.release_id}, Royalty {self.royalty_id}"