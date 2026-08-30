package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/spotbye/SpotiFLAC/backend"
)

func main() {
	query := flag.String("query", "", "Spotify URL or track ID")
	outputDir := flag.String("output", "./downloads", "Output directory")
	flag.Parse()

	if *query == "" {
		if flag.NArg() > 0 {
			*query = flag.Arg(0)
		} else {
			fmt.Println("Usage: spotiflac-cli <spotify-url> [-output <path>]")
			os.Exit(1)
		}
	}

	// Initialize Backend DBs
	if err := backend.InitHistoryDB("SpotiFLAC-CLI"); err != nil {
		log.Printf("Warning: InitHistoryDB: %v", err)
	}
	if err := backend.InitPersistentQueueDB(); err != nil {
		log.Printf("Warning: InitPersistentQueueDB: %v", err)
	}
	if err := backend.InitLibraryIndexDB(); err != nil {
		log.Printf("Warning: InitLibraryIndexDB: %v", err)
	}
	if err := backend.InitISRCCacheDB(); err != nil {
		log.Printf("Warning: InitISRCCacheDB: %v", err)
	}

	absOutput, _ := filepath.Abs(*outputDir)
	os.MkdirAll(absOutput, 0755)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	fmt.Printf("🔍 [SpotiFLAC-CLI] Resolving: %s\n", *query)

	// Fetch Metadata
	metadata, err := backend.GetFilteredSpotifyData(ctx, *query, false, 0, ", ", nil)
	if err != nil {
		log.Fatalf("❌ Metadata error: %v", err)
	}

	// SpotiFLAC usually works by iterating through tracks.
	// The metadata structure returned by GetFilteredSpotifyData depends on the URL type.
	// For a single track, it returns a map.

	app := &backend.App{} // This might need a dummy if it's used as a receiver in some backend functions,
	                      // but usually we call backend functions directly.

	// We'll mimic the app.DownloadTrack logic but for a CLI.
	// We need to construct a DownloadRequest.

	// Simplified logic for a single track download:
	// In a real scenario, we'd handle Albums/Playlists by iterating.

	processTrack := func(track map[string]interface{}) {
		trackName, _ := track["name"].(string)
		artistName, _ := track["artists"].(string)
		spotifyID, _ := track["spotify_id"].(string)

		fmt.Printf("🎵 Downloading: %s - %s\n", artistName, trackName)

		// Attempt download using the preferred service (Tidal is default in app.go)
		// We use Tidal as the primary high-res source for SpotiFLAC.
		downloader := backend.NewTidalDownloader("")

		filename, err := downloader.Download(
			spotifyID,
			absOutput,
			"LOSSLESS",
			"title-artist",
			false, // track number in filename
			0,     // position
			trackName,
			artistName,
			"", // album name
			"", // album artist
			"", // release date
			false, // use album track number
			"", // cover URL
			true, // embed max quality cover
			0, // spotify track number
			0, // spotify disc number
			0, // total tracks
			0, // total discs
			"", // copyright
			"", // publisher
			"", // composer
			", ", // separator
			"", // ISRC
			"", // spotify URL
			true, // allow fallback
			true, // allow atmos fallback
			"LOSSLESS", // atmos quality
			false, // first artist only
			false, // single genre
			true, // embed genre
		)

		if err != nil {
			fmt.Printf("❌ Download failed: %v\n", err)
		} else {
			fmt.Printf("✅ Success: %s\n", filename)
		}
	}

	// Check if it's a single track or a list
	if track, ok := metadata.(map[string]interface{}); ok {
		// Single track
		if _, ok := track["track"]; ok {
			// Some versions wrap it in a "track" key
			if t, ok := track["track"].(map[string]interface{}); ok {
				processTrack(t)
			}
		} else {
			processTrack(track)
		}
	} else if list, ok := metadata.([]interface{}); ok {
		// List of tracks (Playlist/Album)
		for _, item := range list {
			if t, ok := item.(map[string]interface{}); ok {
				processTrack(t)
			}
		}
	} else {
		fmt.Println("⚠️ Unsupported metadata format returned.")
	}
}
