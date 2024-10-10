#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <ctype.h>
#include <filesystem>
#include <vector>
#include <algorithm>
#include <chrono>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define DECLARE_FP(NAME, RETURN_TYPE, ...) \
	typedef RETURN_TYPE(__fastcall* p_##NAME)(__VA_ARGS__); \
	p_##NAME NAME;
#define RUNTIME_LOAD(NAME) NAME = (p_##NAME)GetProcAddress(module, #NAME); ASSERT(NAME, L"Failed to load " L#NAME);
static wchar_t _assert_msg_buffer[1024];
static void _assert(const wchar_t* cond_s, const wchar_t* fmt = L"", auto ...args) {
	int p = swprintf(_assert_msg_buffer, L"Assertion failed: %ls\n", cond_s);
	swprintf(_assert_msg_buffer + p, fmt, args...);
	MessageBoxW(NULL, _assert_msg_buffer, L"Error", MB_ICONERROR); 
	exit(1);	
}
#define ASSERT(cond, ...) if (!cond) _assert(L#cond, __VA_ARGS__);
const wchar_t* HELP_STRING = L"Project SEKAI custom streaming HCA decoder (native win64)\n"
"usage: <input directory (containing *.hca frames)> <output .wav file>\n"
"	- the hca frames will be appended to the wav file one by one whilst being lexicographically sorted by their filenames\n";
struct criware {
	typedef void* handle_t;
	DECLARE_FP(criHcaDecoderUnity_Initialize, handle_t);
	DECLARE_FP(criHcaDecoderUnity_Create, handle_t,
		uint32_t channelCount
	);
	DECLARE_FP(criHcaDecoderUnity_Reset, handle_t,
		handle_t handle, uint32_t channelCount, uint32_t samplingRate, uint32_t bitRate
	);
	DECLARE_FP(criHcaDecoderUnity_DecodeHcaToInterleavedPcm, void,
		handle_t handle, uint8_t* hcaData, uint32_t offset, uint32_t length, float* pcmBuffer, uint32_t* processedLength, uint32_t* outputSampleCount
	);
	criware(LPCWSTR path) {
		HMODULE module = LoadLibraryW(path);
		ASSERT(module, L"Failed to load cri_ware_unity.dll");
		RUNTIME_LOAD(criHcaDecoderUnity_Initialize);
		RUNTIME_LOAD(criHcaDecoderUnity_Create);
		RUNTIME_LOAD(criHcaDecoderUnity_Reset);
		RUNTIME_LOAD(criHcaDecoderUnity_DecodeHcaToInterleavedPcm);
	}
};

// http://soundfile.sapp.org/doc/WaveFormat/
struct wav_writer {
	enum format : uint16_t {
		PCM = 1,
		IEEE_FLOAT = 3,
		ALAW = 6,
		MULAW = 7,
		EXTENSIBLE = 0xFFFE
	};
	struct {
		char RIFF[4]{ 'R','I','F','F' };
		unsigned int ChunkSize;
		char WAVE[4]{ 'W','A','V','E' };
		char fmt[4]{ 'f','m','t',' ' };
		uint32_t Subchunk1Size = 16;
		uint16_t AudioFormat = 1;
		uint16_t ChannelCount;
		uint32_t SampleRate;
		uint32_t ByteRate;
		uint16_t BlockAlign;
		uint16_t BitsPerSample;
		uint8_t Subchunk2ID[4] = { 'd', 'a', 't', 'a' };
		uint32_t Subchunk2Size;
		void update_sample_count(int sampleCountPerChannel) {
			Subchunk2Size = sampleCountPerChannel * ChannelCount * BitsPerSample / 8;
			ChunkSize = 36 + Subchunk2Size;
		}
		void update(format fmt, int channelCount, int sampleRate, int bitsPerSample) {
			AudioFormat = fmt;
			ChannelCount = channelCount;
			SampleRate = sampleRate;
			BitsPerSample = bitsPerSample;
			BlockAlign = BitsPerSample / 8;
			ByteRate = sampleRate * ChannelCount * BitsPerSample / 8;
		}
	} header;
	FILE* fp; int num_samples = 0;
	wav_writer(FILE* fp, format fmt, int channelCount, int sampleRate, int bitsPerSample) : fp(fp) {
		header.update(fmt, channelCount, sampleRate, bitsPerSample);
		fseek(fp, sizeof(header), SEEK_SET);
	}
	void write_mono(const float* pcm32le, const int length) {
		fwrite(pcm32le, sizeof(float), length, fp);
		num_samples += length;
	}
	void flush() {
		header.update_sample_count(num_samples);
		fseek(fp, 0, SEEK_SET);
		fwrite(&header, sizeof(header), 1, fp);
	}
};

#define DIM (size_t)(1e5)
#define FRAME_SIZE_LIMIT 16384
using namespace std;
int main(int argc, char** argv)
{
	if (argc != 3) {
		wprintf(HELP_STRING);
		return 1;
	}
	vector<uint8_t> hcaBuffer(DIM);
	vector<float> pcmBuffer(DIM);

	criware lib(L"cri_ware_unity.dll");
	lib.criHcaDecoderUnity_Initialize();
	criware::handle_t handle = lib.criHcaDecoderUnity_Create(1);
	lib.criHcaDecoderUnity_Reset(handle, 1, 44100, 128000);
	
	FILE* wavfile = fopen(argv[2], "wb");
	ASSERT(wavfile, L"Cannot open output file for writing!");
	wav_writer wav(wavfile, wav_writer::IEEE_FLOAT, 1, 44100, 32);
	// lexicographically sort the entries since we usually have these filenames as prefixes + timestamps
	vector<string> entries;
	for (const auto& entry : filesystem::directory_iterator(argv[1])) 
		if (entry.path().extension() == ".hca")
			entries.push_back(entry.path().string());
	sort(entries.begin(), entries.end());	
	// current timestamp
	auto now_ms = []() { return chrono::duration_cast<chrono::milliseconds>(chrono::system_clock::now().time_since_epoch()).count(); };
	struct { size_t n = 0, t = 0; } p_stat[2];
	auto update_progress = [&](int n = 1, size_t every = 50) {
		p_stat[0].n += n; size_t ts = now_ms();
		size_t dt = ts - p_stat[0].t;
		if (dt >= every || n == 0) {			
			size_t dn = p_stat[0].n - p_stat[1].n;
			float r = dn / (dt / 1000.0f);
			wprintf(L"\rprocessing %05lld/%05lld %.2f frames/s", p_stat[0].n, entries.size(), r);
			p_stat[0].t = ts, p_stat[1] = p_stat[0];
		}
		if (n == 0) wprintf(L"\nall done. going home.\n");
	};
	// write the segments to the output file
	for (const auto& entry : entries) {
		FILE* fp = fopen(entry.c_str(), "rb");
		hcaBuffer.resize(fread(hcaBuffer.data(), 1, DIM, fp));
		ASSERT(hcaBuffer.size() < FRAME_SIZE_LIMIT, L"File=%hs\nFrame size exceeds limit (read=%ld, max=%ld)", entry.c_str(), hcaBuffer.size(), FRAME_SIZE_LIMIT);
		fclose(fp);
		uint32_t processedBytes, outputSamples;
		lib.criHcaDecoderUnity_DecodeHcaToInterleavedPcm(
			handle, hcaBuffer.data(), 0, (int)hcaBuffer.size(), pcmBuffer.data(), &processedBytes, &outputSamples
		);
		pcmBuffer.resize(outputSamples);
		wav.write_mono(pcmBuffer.data(), (int)pcmBuffer.size());
		update_progress(1);
	}
	update_progress(0);
	wav.flush();
	fclose(wavfile);	
	wprintf(L"written to %S\n", argv[2]);
	return 0;
}
