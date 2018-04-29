from atelier.invlib import setup_from_tasks

ns = setup_from_tasks(
    globals(), "appy",
    # languages="en de fr et nl pt-br es".split(),
    # tolerate_sphinx_warnings=True,
    blogref_url = 'http://luc.lino-framework.org',
    revision_control_system='git')
