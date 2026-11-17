#include "D3D12MemAlloc.h"
#include <cstdio>

int main()
{
    D3D12MA::VIRTUAL_BLOCK_DESC blockDescription = {};
    blockDescription.Size = 4096;
    D3D12MA::VirtualBlock *block = nullptr;
    if (FAILED(D3D12MA::CreateVirtualBlock(&blockDescription, &block)) || !block)
        return 1;
    D3D12MA::VIRTUAL_ALLOCATION_DESC description = {};
    description.Size = 64;
    description.Alignment = 16;
    D3D12MA::VirtualAllocation allocation = {};
    UINT64 offset = 0;
    if (FAILED(block->Allocate(&description, &allocation, &offset)) || offset % 16)
        return 2;
    D3D12MA::Statistics statistics = {};
    block->GetStatistics(&statistics);
    if (statistics.AllocationCount != 1 || statistics.AllocationBytes != 64)
        return 3;
    block->FreeAllocation(allocation);
    block->GetStatistics(&statistics);
    if (statistics.AllocationCount || statistics.AllocationBytes)
        return 4;
    block->Release();
    std::puts("PASS D3D12MA3.3 native virtual allocation/alignment/free; no GPU or new Agility SDK required");
}
