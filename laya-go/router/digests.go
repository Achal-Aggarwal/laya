package router

// Per-checkpoint SHA-256 pins: laya/router.py's sha256_digests argument, its LAYA_SHA256_DIGESTS
// layering (_digests_from_env) and the merge of the channels that pin one checkpoint
// (_merge_expected_digests). The Router only holds and merges the maps; the AgentFactory passes
// the result to agent.WithExpectedSHA256, which does the checking.

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"

	"github.com/NandhaKishorM/laya/laya-go/internal/digest"
	"github.com/NandhaKishorM/laya/laya-go/internal/unicodedata"
	"github.com/NandhaKishorM/laya/laya-go/lang"
)

// WithSHA256Digests pins checkpoints to the SHA-256 of their files, one map of slash path -> hex
// digest per checkpoint, as laya's Router(sha256_digests=...) does. Names are normalised as every
// Router name is, so "en" pins English, and a name the Router does not know is an
// *UnknownModelError from New. A nil map is an explicit "pin nothing": it masks a flat
// LAYA_SHA256_DIGESTS for that checkpoint. A pin given here replaces the whole entry the
// environment seeded for that checkpoint; a later call replaces an earlier one per name.
//
// The Router does not verify anything. ExpectedSHA256 says what to hand agent.WithExpectedSHA256.
func WithSHA256Digests(digests map[string]map[string]string) Option {
	digests = copyTable(digests) // later edits by the caller must not reach the Router
	return func(c *config) error {
		names := make([]string, 0, len(digests))
		for name := range digests {
			names = append(names, name)
		}
		sort.Strings(names) // two spellings of one checkpoint ("en", "english") resolve in name order
		for _, name := range names {
			c.digests = append(c.digests, digestPin{name, digests[name]})
		}
		return nil
	}
}

type digestPin struct {
	name  string
	files map[string]string
}

// digestTable is the per-checkpoint pins: a missing key has no entry at all, and a nil value is an
// entry that names no files.
type digestTable map[Checkpoint]map[string]string

// digestsFromEnv is _digests_from_env. A flat {artifact: digest} map, an unset, blank or
// unparseable variable and anything that is not a non-empty object name nothing here: the agent
// reads those itself. A nested {model: {artifact: digest}} map seeds every checkpoint the Router
// knows, the ones it does not name with an empty entry.
func digestsFromEnv(models map[Checkpoint]ModelSpec) (digestTable, error) {
	raw := unicodedata.Strip(os.Getenv(digest.Env))
	if raw == "" {
		return digestTable{}, nil
	}
	var data lang.Object
	if err := json.Unmarshal([]byte(raw), &data); err != nil || len(data) == 0 {
		return digestTable{}, nil // not JSON, not an object, or {}: laya.revisions' to report
	}
	strs, objs := 0, 0
	for _, m := range data {
		switch m.Value.(type) {
		case string:
			strs++
		case lang.Object:
			objs++
		}
	}
	if strs == len(data) {
		return digestTable{}, nil // flat: the agent applies it
	}
	if objs != len(data) {
		keys := make([]string, len(data))
		for i, m := range data {
			keys[i] = m.Key
		}
		return nil, fmt.Errorf("LAYA_SHA256_DIGESTS must be either {artifact: digest} for every "+
			"checkpoint or {model: {artifact: digest}} per checkpoint; %s mixes the two or holds a "+
			"value that is neither", pyList(keys))
	}
	table := make(digestTable, len(models))
	for _, m := range data {
		key, err := NormaliseName(m.Key)
		if err != nil {
			return nil, err
		}
		files := map[string]string{}
		for _, f := range m.Value.(lang.Object) {
			s, ok := f.Value.(string)
			if !ok {
				return nil, fmt.Errorf("LAYA_SHA256_DIGESTS: the digest of %q in %q must be a string, got %T",
					f.Key, m.Key, f.Value)
			}
			files[f.Key] = s
		}
		table[key] = files
	}
	for name := range models {
		if _, ok := table[name]; !ok {
			table[name] = map[string]string{}
		}
	}
	return table, nil
}

// SHA256Digests is a copy of the per-checkpoint pins the Router holds: the environment's, then
// WithSHA256Digests on top. A checkpoint with no entry is absent; one that pins nothing has a nil
// or empty map.
func (r *Router) SHA256Digests() map[Checkpoint]map[string]string { return copyTable(r.digests) }

// copyTable deep-copies a table, keeping a nil entry nil and an empty one empty.
func copyTable[K comparable](t map[K]map[string]string) map[K]map[string]string {
	out := make(map[K]map[string]string, len(t))
	for k, v := range t {
		if v == nil {
			out[k] = nil
			continue
		}
		cp := make(map[string]string, len(v))
		for f, d := range v {
			cp[f] = d
		}
		out[k] = cp
	}
	return out
}

// ExpectedSHA256 is the map to build checkpoint c with, out of the two channels that pin it:
// shared, which reaches every checkpoint (a pin the factory holds itself), and the Router's own
// entry for c. The files of both count, and for a file both name the Router's entry wins, because
// shared reaches checkpoints whose "model.safetensors" are different files.
//
// A nil result means neither channel says anything, and the factory must then pass no
// agent.WithExpectedSHA256, so the agent keeps its own LAYA_SHA256_DIGESTS fallback. An empty
// non-nil result is not the same: it must still be passed, because it masks that fallback, which a
// nested variable would otherwise have read as an artifact map. The result is a fresh map. A name
// the Router does not know is an *UnknownModelError.
func (r *Router) ExpectedSHA256(name string, shared map[string]string) (map[string]string, error) {
	key, err := NormaliseName(name)
	if err != nil {
		return nil, err
	}
	return mergeExpectedDigests(shared, r.digests.entry(key)), nil
}

// entry is _digest_entry: nil when c has no entry, an empty map for one that names no files.
func (t digestTable) entry(c Checkpoint) map[string]string {
	files, ok := t[c]
	if !ok {
		return nil
	}
	if files == nil {
		return map[string]string{}
	}
	return files
}

// mergeExpectedDigests is _merge_expected_digests; nil is None and an empty map is {}.
func mergeExpectedDigests(shared, perModel map[string]string) map[string]string {
	if shared == nil && perModel == nil {
		return nil
	}
	merged := make(map[string]string, len(shared)+len(perModel))
	for k, v := range shared {
		merged[k] = v
	}
	for k, v := range perModel {
		merged[k] = v
	}
	return merged
}
