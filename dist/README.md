# Release bundles

`plan80.plugin` is the Cowork install file. It is the same content as `plugins/plan80/`, zipped. Rebuild it after any change to the plugin:

```bash
cd plugins/plan80 && zip -qr ../../dist/plan80.plugin . -x "*__pycache__*"
```
