# Cleanup — Go Module Cache Fix

Fix for transient `proxy.golang.org` error:
`github.com/gabriel-vasile/mimetype@v1.4.12: stream error: stream ID 39; NO_ERROR`

## Steps

1. Check Go installation and proxy:
   ```bash
   go version
   go env GOPROXY GOSUMDB GOPATH GOROOT
   ```

2. Verify proxy reachability and cached file:
   ```bash
   curl -I https://proxy.golang.org/github.com/gabriel-vasile/mimetype/@v/v1.4.12.zip
   ls -lh $(go env GOPATH)/pkg/mod/cache/download/github.com/gabriel-vasile/mimetype/@v/
   ```

3. Clear Go cache and remove stale lock:
   ```bash
   go clean -cache
   rm -f ~/go/pkg/mod/cache/download/github.com/gabriel-vasile/mimetype/@v/v1.4.12.lock
   ```

4. Re-download bypassing proxy:
   ```bash
   cd buildingsim
   GOPROXY=direct go mod download github.com/gabriel-vasile/mimetype@v1.4.12
   ```

5. Tidy and verify:
   ```bash
   go mod tidy
   go mod download
   go build ./... && echo "build ok"
   ```

6. Optional — persist direct proxy if error recurs:
   ```bash
   go env -w GOPROXY=direct
   # or
   go env -w GOPROXY=https://proxy.golang.org,direct
   ```

## Result

- `go mod tidy` → `tidy ok`
- `go build ./...` → `build ok`
- `make build` succeeds
