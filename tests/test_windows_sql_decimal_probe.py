import pytest
from probe_windows_sql_decimal import project_sources


def test_wrapper_recipe_uses_original_project_compile_inputs(tmp_path):
    source = tmp_path / 'Python'
    project = source / 'PCbuild/_decimal.vcxproj'
    project.parent.mkdir(parents=True)
    (source / 'Modules').mkdir()
    (source / 'Modules/wrapper.c').write_text('/* original wrapper */')
    decimal = tmp_path / 'mpdecimal'
    decimal.mkdir()
    (decimal / 'provider.c').write_text('/* current provider */')
    project.write_text('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
                       '<ItemGroup><ClCompile Include="../Modules/wrapper.c"/>'
                       '<ClCompile Include="$(mpdecimalDir)/provider.c"/></ItemGroup>'
                       '<ItemDefinitionGroup><ClCompile><WarningLevel>4</WarningLevel></ClCompile>'
                       '</ItemDefinitionGroup></Project>')
    assert project_sources(project, source, decimal) == [source / 'Modules/wrapper.c', decimal / 'provider.c']


def test_wrapper_recipe_rejects_source_outside_qualified_trees(tmp_path):
    source = tmp_path / 'Python'
    source.mkdir()
    other = tmp_path / 'foreign.c'
    other.write_text('/* outside source */')
    project = source / 'project.xml'
    project.write_text('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
                       '<ClCompile Include="../foreign.c"/></Project>')
    with pytest.raises(AssertionError):
        project_sources(project, source, tmp_path / 'mpdecimal')
