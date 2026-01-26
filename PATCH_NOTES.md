PHIO PATCH BUNDLE
=================

Contenu
-------
1) .github/workflows/ci.yml
   - CI GitHub Actions (Python 3.11)
   - Installe requirements.txt
   - Vérifie la présence de scripts/phi_otimes_o_instrument_v0_1.py
   - Lance pytest avec INSTRUMENT_PATH=scripts/phi_otimes_o_instrument_v0_1.py

2) scripts/phi_otimes_o_instrument_v0_1.py
   - Instrument stub (spec + fonctions minimales)

3) tests/__init__.py
   - Rend 'tests' importable comme package (utile si conftest/tests utilisent des imports absolus)

Instructions d'intégration
--------------------------
- Copier ces fichiers dans ton repo en respectant les chemins.
- Supprimer tout workflow template non voulu dans .github/workflows (python-package.yml, etc.).
- Si tes tests attendent encore 'pytest_template.json', l'instrument stub doit être enrichi
  selon l'API/contrat exact (nécessite de voir tests/conftest.py + tests/config.py).
