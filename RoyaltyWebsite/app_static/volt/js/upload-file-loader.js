/**
 * Chunked file upload. Default: stereo WAV to /releases/file_uploader/{releaseId}
 * Options: custom uploadUrl, progress container id, skip stereo wave meta check (Dolby Atmos).
 */
class FileUpload {

    constructor(input, options = {}) {
        this.input = input;
        this.max_length = 1024 * 1024 * 10;
        this.uploadUrl = options.uploadUrl || null;
        this.progressContainerId = options.progressContainerId || "uploaded_files";
        this.skipAudioMetaCheck = !!options.skipAudioMetaCheck;
        this.onComplete = typeof options.onComplete === "function" ? options.onComplete : null;
    }

    create_progress_bar() {
        var progress = `<div class="file-icon">
                            <i class="fa fa-file-o" aria-hidden="true"></i>
                        </div>
                        <div class="file-details">
                            <p class="filename"></p>
                            <small class="textbox"></small>
                            <div class="progress" style="margin-top: 5px;">
                                <div class="progress-bar bg-success" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" style="width: 0%">
                                </div>
                            </div>
                        </div>`;
        var el = document.getElementById(this.progressContainerId);
        if (el) {
            el.innerHTML = progress;
        }
    }

    upload(primary_uuid) {
        this._primaryUuid = primary_uuid;
        this.create_progress_bar();
        this.initFileUpload();
    }

    initFileUpload() {
        this.file = this.input.files[0];
        this.upload_file(0, null);
    }

    _progressSelector() {
        var container = document.getElementById(this.progressContainerId);
        if (!container) {
            return $(".progress-bar");
        }
        return $(container).find(".progress-bar");
    }

    _textboxSelector() {
        var container = document.getElementById(this.progressContainerId);
        if (!container) {
            return $(".textbox");
        }
        return $(container).find(".textbox");
    }

    _filenameSelector() {
        var container = document.getElementById(this.progressContainerId);
        if (!container) {
            return $(".filename");
        }
        return $(container).find(".filename");
    }

    upload_file(start, model_id) {
        var end;
        var self = this;
        var existingPath = model_id;
        var formData = new FormData();
        var nextChunk = start + this.max_length + 1;
        var currentChunk = this.file.slice(start, nextChunk);
        var uploadedChunk = start + currentChunk.size;
        if (uploadedChunk >= this.file.size) {
            end = 1;
        } else {
            end = 0;
        }
        formData.append('file', currentChunk);
        formData.append('filename', this.file.name);
        self._textboxSelector().text("Uploading file");
        formData.append('end', end);
        formData.append('existingPath', existingPath);
        formData.append('nextSlice', nextChunk);
        self._filenameSelector().text(this.file.name);

        var postUrl = this.uploadUrl || ("/releases/file_uploader/" + this._primaryUuid);

        var csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        var ajaxHeaders = csrfEl && csrfEl.value ? { 'X-CSRFToken': csrfEl.value } : {};

        $.ajax({
            headers: ajaxHeaders,
            xhr: function () {
                var xhr = new XMLHttpRequest();
                xhr.upload.addEventListener('progress', function (e) {
                    if (e.lengthComputable) {
                        var percent;
                        if (self.file.size < self.max_length) {
                            percent = Math.round((e.loaded / e.total) * 100);
                        } else {
                            percent = Math.round((uploadedChunk / self.file.size) * 100);
                        }
                        self._progressSelector().css('width', percent + '%');
                        self._progressSelector().text(percent + '%');
                    }
                });
                return xhr;
            },

            url: postUrl,
            type: 'POST',
            dataType: 'json',
            cache: false,
            processData: false,
            contentType: false,
            data: formData,
            error: function (xhr) {
                alert(xhr.statusText);
            },
            success: function (res) {
                if (nextChunk < self.file.size) {
                    existingPath = res.existingPath;
                    self.upload_file(nextChunk, existingPath);
                } else {
                    if (!self.skipAudioMetaCheck && existingPath !== null &&
                        (existingPath.split('.')[1] === 'wav' || existingPath.split('.')[1] === 'mp3')) {
                        $.ajax({
                            url: "/releases/tracks_info/check_audio_meta_info/" + existingPath,
                            type: 'GET'
                        }).then(function (response) {
                            if (response.error) {
                                sendSweetAlert('error', '', response.error);
                                document.getElementById("audio_file_track").value = '';
                                self._textboxSelector().text("Upload failed");
                            }
                            if (response.success) {
                                self._textboxSelector().text(res.data);
                                if (typeof self.onComplete === "function") {
                                    try {
                                        self.onComplete(res);
                                    } catch (e) {
                                        console.warn("FileUpload onComplete", e);
                                    }
                                }
                            }
                        });
                    } else {
                        self._textboxSelector().text(res.data);
                        if (typeof self.onComplete === "function") {
                            try {
                                self.onComplete(res);
                            } catch (e) {
                                console.warn("FileUpload onComplete", e);
                            }
                        }
                    }
                }
            }
        });
    }
}
