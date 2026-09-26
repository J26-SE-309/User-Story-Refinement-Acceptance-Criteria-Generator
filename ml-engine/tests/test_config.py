from story_ml import config


def test_data_dir_is_outside_the_repository():
    assert config.DATA_DIR != config.REPO_ROOT
    assert config.REPO_ROOT not in config.DATA_DIR.parents
