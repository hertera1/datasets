import os

import fsspec
import pytest

from datasets.filesystems import COMPRESSION_FILESYSTEMS, HfFileSystem, extract_path_from_uri, is_remote_filesystem
from datasets.utils._hf_hub_fixes import dataset_info as hf_api_dataset_info

from .utils import require_lz4, require_zstandard


def test_extract_path_from_uri():
    mock_bucket = "mock-s3-bucket"
    dataset_path = f"s3://{mock_bucket}"
    dataset_path = extract_path_from_uri(dataset_path)
    assert dataset_path.startswith("s3://") is False

    dataset_path = "./local/path"
    new_dataset_path = extract_path_from_uri(dataset_path)
    assert dataset_path == new_dataset_path


def test_is_remote_filesystem(mockfs):
    is_remote = is_remote_filesystem(mockfs)
    assert is_remote is True

    fs = fsspec.filesystem("file")

    is_remote = is_remote_filesystem(fs)
    assert is_remote is False


@pytest.mark.parametrize("compression_fs_class", COMPRESSION_FILESYSTEMS)
def test_compression_filesystems(compression_fs_class, gz_file, bz2_file, lz4_file, zstd_file, xz_file, text_file):
    input_paths = {"gzip": gz_file, "xz": xz_file, "zstd": zstd_file, "bz2": bz2_file, "lz4": lz4_file}
    input_path = input_paths[compression_fs_class.protocol]
    if input_path is None:
        reason = f"for '{compression_fs_class.protocol}' compression protocol, "
        if compression_fs_class.protocol == "lz4":
            reason += require_lz4.kwargs["reason"]
        elif compression_fs_class.protocol == "zstd":
            reason += require_zstandard.kwargs["reason"]
        pytest.skip(reason)
    fs = fsspec.filesystem(compression_fs_class.protocol, fo=input_path)
    assert isinstance(fs, compression_fs_class)
    expected_filename = os.path.basename(input_path)
    expected_filename = expected_filename[: expected_filename.rindex(".")]
    assert fs.ls("/") == [expected_filename]
    with fs.open(expected_filename, "r", encoding="utf-8") as f, open(text_file, encoding="utf-8") as expected_file:
        assert f.read() == expected_file.read()


@pytest.mark.parametrize("protocol", ["zip", "gzip"])
def test_fs_isfile(protocol, zip_jsonl_path, jsonl_gz_path):
    compressed_file_paths = {"zip": zip_jsonl_path, "gzip": jsonl_gz_path}
    compressed_file_path = compressed_file_paths[protocol]
    member_file_path = "dataset.jsonl"
    path = f"{protocol}://{member_file_path}::{compressed_file_path}"
    fs, *_ = fsspec.get_fs_token_paths(path)
    assert fs.isfile(member_file_path)
    assert not fs.isfile("non_existing_" + member_file_path)


@pytest.mark.integration
def test_hf_filesystem(hf_token, hf_api, hf_private_dataset_repo_txt_data, text_file):
    repo_info = hf_api_dataset_info(hf_api, hf_private_dataset_repo_txt_data, use_auth_token=hf_token)
    hffs = HfFileSystem(repo_info=repo_info, token=hf_token)
    assert sorted(hffs.glob("*")) == [".gitattributes", "data"]
    assert hffs.isdir("data")
    assert hffs.isfile(".gitattributes") and hffs.isfile("data/text_data.txt")
    with open(text_file) as f:
        assert hffs.open("data/text_data.txt", "r").read() == f.read()
