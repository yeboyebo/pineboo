import os, os.path, sys
import math
from optparse import OptionParser
import difflib 
import re

class ProcessFile:
    def __init__(self, filename):
        self.filename = filename
        self.process()
        self.indexLines()
        self.bnames = set(self.idxnames.keys())

    def process(self):
        self.blocks = []
        self.idxlines = {}
        self.idxnames = {}
        self.sortednames = []
        
        fblocks = open(self.filename + ".blocks")
        n = 0
        line = fblocks.readline()
        while line:
            start, end, name = line.strip().split("\t")
            self.blocks.append( (start,end, name) )
            self.idxlines[start] = n
            self.sortednames.append(name)
            if name in self.idxnames:
                self.idxnames[name] = None
            else:
                self.idxnames[name] = n
            n+=1
            line = fblocks.readline()
            
    def indexLines(self):
        fqs = open(self.filename)
        self.lines = []
        for line in fqs:
            self.lines.append(line)
        
        
    
    def diffTo(self,pfile2):
        added = pfile2.bnames - self.bnames
        deleted = self.bnames - pfile2.bnames
        
        return added, deleted
        
        
def appliedDiff(C, A, B, prefer = "C", debug = False, quiet = False):
    diffAB = list(difflib.ndiff(A.sortednames, B.sortednames))
    diffAC = list(difflib.ndiff(A.sortednames, C.sortednames))
    
    nlA = 0
    nlB = 0
    nlC = 0
    nlAB = 0
    nlAC = 0
    
    maxA = len(A.sortednames)
    maxB = len(B.sortednames)
    maxC = len(C.sortednames)
    
    patchedResult = []
    
    def AddPatchLine(mode):
        modefrom = mode[0]
        modetype = mode[1]
        linefrom = None
        linetext = ""
        linenumbers = nlA,nlB,nlC 
        if modetype == "-":
            linetext = lineaA
            linefrom = "A"
        elif modetype == "=":
            modefrom = prefer
            if modefrom == "A":
                linetext = lineaA
            elif modefrom == "B":
                linetext = lineaB
            elif modefrom == "C":
                linetext = lineaC
            linefrom = modefrom
        elif modetype == "+":
            if modefrom == "A":
                linetext = lineaA
            elif modefrom == "B":
                linetext = lineaB
            elif modefrom == "C":
                linetext = lineaC
            linefrom = modefrom
        line = (
            modefrom, modetype,
            linenumbers,
            linefrom,
            linetext
        )
        patchedResult.append(line)
        
    
            
    while True:
        if (
            nlA >= maxA and 
            nlB >= maxB and 
            nlC >= maxC
            ): break
        if nlA >= maxA : lineaA = " "
        else: lineaA = A.sortednames[nlA]
        
        if nlB >= maxB : 
            sAB = cAB = lineaA = " "
        else:
            lineaB = B.sortednames[nlB]
            sAB = diffAB[nlAB][0]
            cAB = diffAB[nlAB][2:]
            
        if nlC >= maxC : 
            sAC = cAC = lineaC = " "
        else:
            lineaC = C.sortednames[nlC]
            sAC = diffAC[nlAC][0]
            cAC = diffAC[nlAC][2:]
        #print nlA, nlB, nlC
        if sAB == " " and sAC == " ":
            AddPatchLine("A=")
            if debug:
                if prefer == "":
                    print "ABC=%04d%+d%+d" % (nlA,nlB-nlA,nlC-nlA),lineaA
                elif prefer == "A":
                    print "A=%04d" % nlA,lineaA
                elif prefer == "B":
                    print "B=%04d" % nlB,lineaB
                elif prefer == "C":
                    print "C=%04d" % nlC,lineaC
                else:
                    assert prefer in ["A","B","C"]
            if not quiet:
                if lineaA!=cAB:
                    print "B!    " , cAB
                if lineaA!=cAC:
                    print "C!    " , cAC
                if lineaA != lineaB or lineaC != lineaA:
                    print "wtf!?"
                
            nlAB += 1
            nlAC += 1
            nlA += 1
            nlB += 1
            nlC += 1
        elif sAB=="+":
            AddPatchLine("B+")
            if debug:
                print "B+%04d" % nlB, lineaB
            if lineaB!=cAB and not quiet:
                print "B!    " , cAB
                
            nlAB += 1
            nlB += 1
        elif sAB=="?":
            nlAB += 1
            if debug:
                print "?>    " , cAB
            
        elif sAC=="+":
            AddPatchLine("C+")
            if debug:
                print "C+%04d" % nlC, lineaC
            if not quiet and lineaC!=cAC:
                print "C!    " , cAC
            nlAC += 1
            nlC += 1
        elif sAC=="?":
            nlAC += 1
            if debug:
                print "?>    " , cAC
        elif sAB=="-":
            AddPatchLine("B-")
            if debug:
                print "B-%04d" % nlA, lineaA
            if lineaA!=cAB and not quiet:
                print "B!    " , cAB
            if sAC!=" " and not quiet:
                print "?? C", sAC,cAC
            nlAB += 1
            nlAC += 1
            nlA += 1
            nlC += 1
        elif sAC=="-":
            AddPatchLine("C-")
            if debug:
                print "C-%04d" % nlA, lineaA
            if lineaA!=cAC and not quiet:
                print "C!    " , cAC
            if sAB!=" " and not quiet:
                print "?? B", sAB,cAB
            nlAC += 1
            nlAB += 1
            nlA += 1
            nlB += 1
        else:
            if not quiet:
                print sAB,"*", sAC
            break
        
            
        
        
    
    return patchedResult
    """
    added, deleted = pfrom.diffTo(pto)
    plist = []
    for start,end,name in ptarget.blocks:
        if name in added:
            n = pto.idxnames[name]
            if n is not None:
                start,end,name = pto.blocks[n]
                bobject = pto.filename
            else:
                print "Conflict with element", name
        elif name in deleted:
            bobject = "deleted"
            plist.append((bobject,start,end,name))
        else:
            bobject = ptarget.filename
            plist.append((bobject,start,end,name))
    
    return plist
"""

def writeAlignedFile(C, A, B, prefer = "C", debug = False, quiet = False):
    patchlist = appliedDiff(C, A, B)
    F = {"A": A, "B": B, "C": C}        
    L = ["A", "B", "C"]        
    fout = open(C.filename + ".aligned","w")
    
    for Fby,action, nlines, Fwhich, line in patchlist:
        nlA, nlB, nlC = nlines
        if action not in ("+","="): continue
        nl = nlines[L.index(Fwhich)]
        linebegin, lineend, line = F[Fwhich].blocks[nl]
        
        text = "".join(
                F[Fwhich].lines[int(linebegin):int(lineend)]
            )
        if debug:
            fout.write("<<< %s (%d:%d) || %s >>>\n" % (Fwhich,int(linebegin),int(lineend), line))
        fout.write(text)
        
    
    fout.close()
    
def main():
    parser = OptionParser()
    parser.add_option("-q", "--quiet",
                    action="store_false", dest="verbose", default=True,
                    help="don't print status messages to stdout")

    parser.add_option("--optdebug",
                    action="store_true", dest="optdebug", default=False,
                    help="debug optparse module")

    (options, args) = parser.parse_args()
    if options.optdebug:
        print options, args

    filenames = filter(lambda x: os.path.isfile(x) , args)
    not_a_file = set(args) - set(filenames)
    if len(not_a_file):
        print "WARNING: Not a file:", ", ".join(not_a_file)
        return

    if len(filenames) != 3:
        print "MUST have exactly 3 files to align."
    pfiles = []        
    for file1 in filenames:
        print "Load File:", file1
        pf = ProcessFile(file1)
        pfiles.append(pf)

    A = pfiles[0]
    B = pfiles[1]
    C = pfiles[2]
           
    #addedAB, deletedAB = A.diffTo(B)
    #addedAC, deletedAC = A.diffTo(C)
    
    writeAlignedFile(C, A, B)
    writeAlignedFile(B, A, C)
    writeAlignedFile(A, A, C)
        
        
if __name__ == "__main__": main()        