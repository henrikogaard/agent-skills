#!/usr/bin/env ruby

require "json"
require "fileutils"
require "minitest/autorun"
require "open3"
require "tmpdir"

require_relative "../lib/agent_skills/catalog"

class SkillsCliTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  CLI = File.join(ROOT, "scripts", "skills")

  def run_cli(*args, env: {})
    Open3.capture3(env, "ruby", CLI, *args, chdir: ROOT)
  end

  def test_validate_accepts_the_repository_manifest
    stdout, stderr, status = run_cli("validate", "--format", "json")

    assert status.success?, stderr
    result = JSON.parse(stdout)
    assert_equal "ok", result.fetch("status")
    assert_equal 26, result.fetch("skills")
    assert_empty result.fetch("errors")
  end

  def test_legacy_validator_uses_the_manifest_contract
    stdout, stderr, status = Open3.capture3("ruby", File.join(ROOT, "scripts", "validate-skills.rb"), chdir: ROOT)

    assert status.success?, stderr
    assert_includes stdout, "manifest"
  end

  def test_readme_documents_the_manifest_workflow_and_current_portable_path
    readme = File.read(File.join(ROOT, "README.md"))

    assert_includes readme, "scripts/skills inventory"
    assert_includes readme, "scripts/skills plan"
    assert_includes readme, "~/.agents/skills"
    refute_includes readme, "~/.config/opencode/skill"
  end

  def test_validate_rejects_a_codex_skill_outside_the_platform_overlay
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "codex-demo", "codex-demo")
      FileUtils.mkdir_p(File.join(root, "config"))
      File.write(File.join(root, "config", "skills.yaml"), <<~YAML)
        schema_version: 1
        skills:
          codex-demo:
            path: codex-demo
            class: codex
            targets: [codex]
            ownership: first-party
            publication: public
            update_policy: repository
        external_capabilities: []
      YAML
      File.write(File.join(root, "README.md"), "[`codex-demo`](codex-demo/SKILL.md)\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "codex-demo: Codex skills must live under platforms/codex"
    end
  end

  def test_validate_rejects_non_first_party_skills
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo", ownership: "vendored-third-party")
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "demo: ownership must be first-party"
    end
  end

  def test_validate_rejects_vendor_directories_in_the_public_repository
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "vendor/demo", "demo")
      write_fixture_manifest(root, "demo", "vendor/demo")
      File.write(File.join(root, "README.md"), "[`demo`](vendor/demo/SKILL.md)\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "filesystem: public repository must not contain vendor/"
    end
  end

  def test_validate_rejects_internal_hosting_metadata
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n")
      FileUtils.mkdir_p(File.join(root, ".openai"))
      File.write(File.join(root, ".openai", "hosting.json"), "{}\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "filesystem: public repository must not contain .openai/"
    end
  end

  def test_validate_rejects_sensitive_filenames
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n")
      File.write(File.join(root, ".env"), "EXAMPLE_ONLY=true\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "public-safety: sensitive file .env is not allowed"
    end
  end

  def test_validate_rejects_secret_signatures_without_echoing_the_value
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      token = "github" + "_pat_" + ("A" * 82)
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n#{token}\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "public-safety: README.md contains a GitHub token signature"
      refute errors.any? { |error| error.include?(token) }
    end
  end

  def test_validate_rejects_machine_specific_paths_and_private_hosts
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      private_path = File.join(File::SEPARATOR, "Users", "private", "work")
      private_host = "https://git.chatgpt-team" + ".site/internal"
      File.write(
        File.join(root, "README.md"),
        "[`demo`](demo/SKILL.md)\n#{private_path}\n#{private_host}\n"
      )

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "public-safety: README.md contains a machine-specific absolute path"
      assert_includes errors, "public-safety: README.md contains a private hosting endpoint"
    end
  end

  def test_validate_rejects_stale_relative_readme_links
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      File.write(File.join(root, "README.md"), <<~MARKDOWN)
        [`demo`](demo/SKILL.md)
        [Missing documentation](docs/missing.md)
      MARKDOWN

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "README: missing relative link target docs/missing.md"
    end
  end

  def test_validate_rejects_nonportable_skill_names
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "Bad_Name", "Bad_Name")
      write_fixture_manifest(root, "Bad_Name", "Bad_Name")
      File.write(File.join(root, "README.md"), "[`Bad_Name`](Bad_Name/SKILL.md)\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "Bad_Name: name must use lowercase alphanumeric words separated by single hyphens"
    end
  end

  def test_validate_preserves_the_missing_manifest_error
    Dir.mktmpdir do |root|
      File.write(File.join(root, "README.md"), "")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "manifest: missing config/skills.yaml"
    end
  end

  def test_validate_reports_nonmapping_skill_frontmatter_without_crashing
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n")
      File.write(File.join(root, "demo", "SKILL.md"), "---\n- invalid\n- frontmatter\n---\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "demo: YAML frontmatter must be a mapping"
    end
  end

  def test_validate_reports_nonmapping_openai_metadata_without_crashing
    Dir.mktmpdir do |root|
      write_fixture_skill(root, "demo", "demo")
      write_fixture_manifest(root, "demo", "demo")
      File.write(File.join(root, "README.md"), "[`demo`](demo/SKILL.md)\n")
      File.write(File.join(root, "demo", "agents", "openai.yaml"), "- invalid\n- metadata\n")

      errors = AgentSkills::Catalog.new(root).validate

      assert_includes errors, "demo: agents/openai.yaml must be a mapping"
    end
  end

  def test_inventory_lists_repository_skills_without_writing_to_install_roots
    Dir.mktmpdir do |temp|
      agents_root = File.join(temp, "agents")
      codex_root = File.join(temp, "codex")

      stdout, stderr, status = run_cli(
        "inventory", "--format", "json",
        "--agents-root", agents_root,
        "--codex-root", codex_root
      )

      assert status.success?, stderr
      result = JSON.parse(stdout)
      assert_equal 26, result.fetch("repository").length
      assert_equal({ "agents" => agents_root, "codex" => codex_root }, result.fetch("roots"))
      refute File.exist?(agents_root)
      refute File.exist?(codex_root)
    end
  end

  def test_text_inventory_lists_each_skill_state
    Dir.mktmpdir do |temp|
      stdout, stderr, status = run_cli(
        "inventory",
        "--agents-root", File.join(temp, "agents"),
        "--codex-root", File.join(temp, "codex")
      )

      assert status.success?, stderr
      assert_includes stdout, "missing agents:summary-tables"
      assert_includes stdout, "inventory: current=0 missing=26 drifted=0 unmanaged=0 duplicates=0"
    end
  end

  def test_status_reports_missing_skills_with_a_nonzero_exit
    Dir.mktmpdir do |temp|
      stdout, _stderr, status = run_cli(
        "status", "--format", "json",
        "--agents-root", File.join(temp, "agents"),
        "--codex-root", File.join(temp, "codex")
      )

      refute status.success?
      result = JSON.parse(stdout)
      assert_equal 26, result.dig("summary", "missing")
      assert_equal 0, result.dig("summary", "current")
      assert_equal "drift", result.fetch("status")
    end
  end

  def test_plan_is_read_only_and_blocks_drift_and_unmanaged_removals
    Dir.mktmpdir do |temp|
      agents_root = File.join(temp, "agents")
      codex_root = File.join(temp, "codex")
      FileUtils.mkdir_p([agents_root, codex_root])

      copy_skill("summary-tables", agents_root)
      copy_skill("requirements-spec", agents_root)
      File.open(File.join(agents_root, "requirements-spec", "SKILL.md"), "a") { |file| file << "\nlocal drift\n" }
      copy_skill("summary-router", codex_root)
      unmanaged = File.join(agents_root, "local-only")
      FileUtils.mkdir_p(unmanaged)
      File.write(File.join(unmanaged, "SKILL.md"), "---\nname: local-only\ndescription: local\n---\n")
      before = tree_snapshot(temp)

      stdout, stderr, status = run_cli(
        "plan", "--format", "json",
        "--agents-root", agents_root,
        "--codex-root", codex_root
      )

      assert status.success?, stderr
      result = JSON.parse(stdout)
      actions = result.fetch("actions")
      assert_equal 24, actions.count { |action| action.fetch("action") == "add" }
      blocked = actions.map { |action| action["name"] if action["action"] == "blocked_drift" }.compact
      assert_equal ["requirements-spec"], blocked
      warnings = result.fetch("warnings")
      assert warnings.any? { |warning| warning["kind"] == "unmanaged" && warning["name"] == "local-only" }
      assert warnings.any? { |warning| warning["kind"] == "duplicate" && warning["name"] == "summary-router" }
      assert_equal before, tree_snapshot(temp)
    end
  end

  def test_status_ignores_runtime_cache_files_inside_an_installed_skill
    Dir.mktmpdir do |temp|
      agents_root = File.join(temp, "agents")
      codex_root = File.join(temp, "codex")
      FileUtils.mkdir_p([agents_root, codex_root])
      copy_skill("delegated-subagents", agents_root)
      cache = File.join(agents_root, "delegated-subagents", "scripts", "__pycache__")
      FileUtils.mkdir_p(cache)
      File.binwrite(File.join(cache, "runtime.pyc"), "generated cache")
      File.binwrite(File.join(agents_root, "delegated-subagents", ".DS_Store"), "generated metadata")

      stdout, stderr, _status = run_cli(
        "status", "--format", "json",
        "--agents-root", agents_root,
        "--codex-root", codex_root
      )

      assert_empty stderr
      result = JSON.parse(stdout)
      delegated = result.fetch("skills").find { |skill| skill.fetch("name") == "delegated-subagents" }
      assert_equal "current", delegated.fetch("state")
    end
  end

  private

  def copy_skill(name, target_root)
    FileUtils.cp_r(File.join(ROOT, name), File.join(target_root, name))
  end

  def write_fixture_skill(root, path, name)
    skill_root = File.join(root, path)
    FileUtils.mkdir_p(File.join(skill_root, "agents"))
    File.write(File.join(skill_root, "SKILL.md"), <<~MARKDOWN)
      ---
      name: #{name}
      description: Fixture skill
      ---
    MARKDOWN
    File.write(File.join(skill_root, "agents", "openai.yaml"), <<~YAML)
      interface:
        display_name: Fixture
        short_description: Fixture
        default_prompt: Use fixture
      policy:
        allow_implicit_invocation: false
    YAML
  end

  def write_fixture_manifest(root, name, path, ownership: "first-party")
    FileUtils.mkdir_p(File.join(root, "config"))
    File.write(File.join(root, "config", "skills.yaml"), <<~YAML)
      schema_version: 1
      skills:
        #{name}:
          path: #{path}
          class: portable
          targets: [agents]
          ownership: #{ownership}
          publication: public
          update_policy: repository
      external_capabilities: []
    YAML
  end

  def tree_snapshot(root)
    Dir.glob(File.join(root, "**", "*"), File::FNM_DOTMATCH).sort.to_h do |path|
      relative = path.delete_prefix("#{root}/")
      [relative, File.file?(path) ? File.binread(path) : :directory]
    end
  end
end
