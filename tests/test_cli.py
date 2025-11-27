"""
Tests for CLI commands.
"""

import pytest
import sys
import importlib
from click.testing import CliRunner
from pathlib import Path
import json

from et_intel_core.models import MonitoredEntity, Comment, Post, ExtractedSignal
from et_intel_core.models.enums import EntityType, PlatformType


# Helper function for CLI mocking
def setup_cli_mocks(monkeypatch, test_session):
    """Set up mocks for CLI database functions."""
    from et_intel_core import db
    
    def mock_init_db():
        from et_intel_core.models.base import Base
        Base.metadata.create_all(bind=test_session.bind)
    
    def mock_drop_db():
        from et_intel_core.models.base import Base
        Base.metadata.drop_all(bind=test_session.bind)
    
    monkeypatch.setattr(db, 'init_db', mock_init_db)
    monkeypatch.setattr(db, 'drop_db', mock_drop_db)
    monkeypatch.setattr(db, 'get_session', lambda: test_session)
    
    # Reload cli module to pick up mocks
    if 'cli' in sys.modules:
        importlib.reload(sys.modules['cli'])
    
    from cli import cli
    return cli


@pytest.fixture
def runner(monkeypatch, test_session):
    """Create a CLI test runner with mocked database functions."""
    # Ensure cli module uses mocked functions
    import sys
    if 'cli' in sys.modules:
        from cli import cli as cli_module
        from et_intel_core import db
        
        def mock_init_db():
            from et_intel_core.models.base import Base
            try:
                Base.metadata.create_all(bind=test_session.bind)
            except Exception:
                pass
        
        def mock_drop_db():
            from et_intel_core.models.base import Base
            Base.metadata.drop_all(bind=test_session.bind)
        
        monkeypatch.setattr(db, 'init_db', mock_init_db)
        monkeypatch.setattr(db, 'drop_db', mock_drop_db)
        monkeypatch.setattr(db, 'get_session', lambda: test_session)
    
    return CliRunner()


@pytest.fixture
def sample_seed_file(tmp_path):
    """Create a sample seed entities JSON file."""
    seed_data = [
        {
            "name": "Test Person",
            "canonical_name": "Test Person",
            "entity_type": "person",
            "aliases": ["TP", "Test"]
        },
        {
            "name": "Test Show",
            "canonical_name": "Test Show",
            "entity_type": "show",
            "aliases": []
        }
    ]
    
    seed_file = tmp_path / "seed.json"
    with open(seed_file, 'w') as f:
        json.dump(seed_data, f)
    
    return seed_file


class TestInitCommand:
    """Tests for init command."""
    
    def test_init_creates_tables(self, runner, test_session, monkeypatch):
        """Test that init command creates database tables."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        
        result = runner.invoke(cli, ['init'])
        # Check for success message (case-insensitive, handle emoji encoding issues)
        output_lower = result.output.lower()
        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert "initialized" in output_lower or "success" in output_lower
    
    def test_init_with_force(self, runner, test_session, monkeypatch):
        """Test init with --force flag."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        
        # First init
        runner.invoke(cli, ['init'])
        
        # Force reinit
        result = runner.invoke(cli, ['init', '--force'], input='y\n')
        assert result.exit_code == 0


class TestStatusCommand:
    """Tests for status command."""
    
    def test_status_empty_database(self, runner, test_session, monkeypatch):
        """Test status command on empty database."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['status'])
        assert result.exit_code == 0
        assert "Database Status" in result.output or "Posts:" in result.output or "Comments:" in result.output
    
    def test_status_with_data(self, runner, test_session, sample_post, sample_comment, monkeypatch):
        """Test status command with data."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['status'])
        assert result.exit_code == 0
        assert "1" in result.output  # Should show 1 post and 1 comment
    
    def test_status_detailed(self, runner, test_session, sample_post, sample_comment, monkeypatch):
        """Test status command with --detailed flag."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['status', '--detailed'])
        assert result.exit_code == 0
        assert "Database Status" in result.output or "Posts:" in result.output


class TestSeedEntitiesCommand:
    """Tests for seed-entities command."""
    
    def test_seed_entities_success(self, runner, test_session, sample_seed_file, monkeypatch):
        """Test seeding entities from JSON file."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['seed-entities', '--file', str(sample_seed_file)])
        assert result.exit_code == 0
        assert "Test Person" in result.output or "Test Show" in result.output
        
        # Verify entities were created
        entities = test_session.query(MonitoredEntity).all()
        assert len(entities) == 2
    
    def test_seed_entities_duplicate(self, runner, test_session, sample_seed_file, monkeypatch):
        """Test seeding entities twice (should skip duplicates)."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        # First seed
        runner.invoke(cli, ['seed-entities', '--file', str(sample_seed_file)])
        
        # Second seed (should skip)
        result = runner.invoke(cli, ['seed-entities', '--file', str(sample_seed_file)])
        assert result.exit_code == 0
        assert "Skipped" in result.output or "already" in result.output.lower() or "exists" in result.output.lower()
    
    def test_seed_entities_file_not_found(self, runner, test_session, monkeypatch):
        """Test seed-entities with non-existent file."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['seed-entities', '--file', 'nonexistent.json'])
        assert result.exit_code != 0


class TestAddEntityCommand:
    """Tests for add-entity command."""
    
    def test_add_entity_success(self, runner, test_session, monkeypatch):
        """Test adding a new entity."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['add-entity', 'New Person', '--type', 'person'])
        assert result.exit_code == 0
        assert "Added" in result.output or "added" in result.output.lower()
        
        # Verify entity was created
        entity = test_session.query(MonitoredEntity).filter_by(name='New Person').first()
        assert entity is not None
        assert entity.entity_type == EntityType.PERSON
    
    def test_add_entity_with_aliases(self, runner, test_session, monkeypatch):
        """Test adding entity with aliases."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, [
            'add-entity', 'Test Person',
            '--type', 'person',
            '--aliases', 'TP',
            '--aliases', 'Test'
        ])
        assert result.exit_code == 0
        
        entity = test_session.query(MonitoredEntity).filter_by(name='Test Person').first()
        assert entity is not None
        assert 'TP' in entity.aliases
        assert 'Test' in entity.aliases
    
    def test_add_entity_duplicate(self, runner, test_session, monkeypatch):
        """Test adding duplicate entity."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        # Add first time
        runner.invoke(cli, ['add-entity', 'Duplicate', '--type', 'person'])
        
        # Try to add again
        result = runner.invoke(cli, ['add-entity', 'Duplicate', '--type', 'person'])
        assert result.exit_code == 0
        assert "already exists" in result.output.lower() or "duplicate" in result.output.lower()


class TestReviewEntitiesCommand:
    """Tests for review-entities command."""
    
    def test_review_entities_empty(self, runner, test_session, monkeypatch):
        """Test review-entities with no discovered entities."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['review-entities'])
        assert result.exit_code == 0
        assert "No new entities" in result.output or "All caught up" in result.output or "No discovered" in result.output
    
    def test_review_entities_with_data(self, runner, test_session, sample_discovered_entity, monkeypatch):
        """Test review-entities with discovered entities."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['review-entities', '--min-mentions', '1'])
        assert result.exit_code == 0
        assert sample_discovered_entity.name in result.output


class TestTopEntitiesCommand:
    """Tests for top-entities command."""
    
    def test_top_entities_empty(self, runner, test_session, monkeypatch):
        """Test top-entities with no data."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['top-entities'])
        assert result.exit_code == 0
        assert "No entity data" in result.output or "No data found" in result.output or "No entities" in result.output
    
    def test_top_entities_with_data(self, runner, test_session, enriched_comment, sample_entity, monkeypatch):
        """Test top-entities with enriched data."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        # Ensure entity is attached to session
        test_session.refresh(sample_entity)
        result = runner.invoke(cli, ['top-entities', '--days', '30'])
        assert result.exit_code == 0
        # Should show entity name
        assert sample_entity.name in result.output


class TestVelocityCommand:
    """Tests for velocity command."""
    
    def test_velocity_entity_not_found(self, runner, test_session, monkeypatch):
        """Test velocity for non-existent entity."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['velocity', 'Nonexistent Entity'])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()
    
    def test_velocity_insufficient_data(self, runner, test_session, sample_entity, monkeypatch):
        """Test velocity with insufficient data."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['velocity', sample_entity.name])
        assert result.exit_code == 0
        # Should show error about insufficient data
        assert "error" in result.output.lower() or "insufficient" in result.output.lower()


class TestSentimentHistoryCommand:
    """Tests for sentiment-history command."""
    
    def test_sentiment_history_entity_not_found(self, runner, test_session, monkeypatch):
        """Test sentiment-history for non-existent entity."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['sentiment-history', 'Nonexistent Entity'])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()
    
    def test_sentiment_history_no_data(self, runner, test_session, sample_entity, monkeypatch):
        """Test sentiment-history with no data."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['sentiment-history', sample_entity.name])
        assert result.exit_code == 0
        assert "No sentiment history" in result.output or "not found" in result.output.lower() or "No data" in result.output


class TestCreateIndexesCommand:
    """Tests for create-indexes command."""
    
    def test_create_indexes(self, runner, test_session, monkeypatch):
        """Test creating performance indexes."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['create-indexes'])
        assert result.exit_code == 0
        assert "created" in result.output.lower() or "already exists" in result.output.lower() or "index" in result.output.lower()


class TestVersionCommand:
    """Tests for version command."""
    
    def test_version_shows_info(self, runner, monkeypatch, test_session):
        """Test version command shows system information."""
        cli = setup_cli_mocks(monkeypatch, test_session)
        result = runner.invoke(cli, ['version'])
        assert result.exit_code == 0
        assert "2.0.0" in result.output or "Version" in result.output
        assert "Python" in result.output or "python" in result.output.lower()

