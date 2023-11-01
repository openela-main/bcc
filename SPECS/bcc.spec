# We don't want to bring luajit in RHEL
%if 0%{?rhel} > 0
%bcond_with lua
%else
# luajit is not available for some architectures
%ifarch ppc64 ppc64le s390x
%bcond_with lua
%else
%bcond_without lua
%endif
%endif

%ifarch x86_64 ppc64 ppc64le aarch64
%bcond_without libbpf_tools
%else
%bcond_with libbpf_tools
%endif

%bcond_with llvm_static

%if %{without llvm_static}
%global with_llvm_shared 1
%endif


Name:           bcc
Version:        0.25.0
Release:        2%{?dist}
Summary:        BPF Compiler Collection (BCC)
License:        ASL 2.0
URL:            https://github.com/iovisor/bcc
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch0:         %%{name}-%%{version}-bcc-support-building-with-external-libbpf-package-an.patch
Patch2:         %%{name}-%%{version}-Fix-bpf_pseudo_fd-type-conversion-error.patch
Patch3:         %%{name}-%%{version}-Fix-clang-15-int-to-pointer-conversion-errors.patch
Patch4:         %%{name}-%%{version}-Fix-some-documentation-issues-4197.patch
Patch5:         %%{name}-%%{version}-tools-nfsslower-fix-an-uninitialized-struct-error.patch

# Arches will be included as upstream support is added and dependencies are
# satisfied in the respective arches
ExclusiveArch:  x86_64 %{power64} aarch64 s390x armv7hl

BuildRequires:  bison
BuildRequires:  cmake >= 2.8.7
BuildRequires:  flex
BuildRequires:  libxml2-devel
BuildRequires:  python3-devel
BuildRequires:  elfutils-libelf-devel
BuildRequires:  elfutils-debuginfod-client-devel
BuildRequires:  llvm-devel
BuildRequires:  clang-devel
%if %{with llvm_static}
BuildRequires:  llvm-static
%endif
BuildRequires:  ncurses-devel
%if %{with lua}
BuildRequires:  pkgconfig(luajit)
%endif
BuildRequires:  libbpf-devel >= 2:0.8.0, libbpf-static >= 2:0.8.0

Requires:       libbpf >= 2:0.8.0
Requires:       tar
Recommends:     kernel-devel

Recommends:     %{name}-tools = %{version}-%{release}

%description
BCC is a toolkit for creating efficient kernel tracing and manipulation
programs, and includes several useful tools and examples. It makes use of
extended BPF (Berkeley Packet Filters), formally known as eBPF, a new feature
that was first added to Linux 3.15. BCC makes BPF programs easier to write,
with kernel instrumentation in C (and includes a C wrapper around LLVM), and
front-ends in Python and lua. It is suited for many tasks, including
performance analysis and network traffic control.


%package devel
Summary:        Shared library for BPF Compiler Collection (BCC)
Requires:       %{name}%{?_isa} = %{version}-%{release}
Suggests:       elfutils-debuginfod-client

%description devel
The %{name}-devel package contains libraries and header files for developing
application that use BPF Compiler Collection (BCC).


%package doc
Summary:        Examples for BPF Compiler Collection (BCC)
Recommends:     python3-%{name} = %{version}-%{release}
Recommends:     %{name}-lua = %{version}-%{release}
BuildArch:      noarch

%description doc
Examples for BPF Compiler Collection (BCC)


%package -n python3-%{name}
Summary:        Python3 bindings for BPF Compiler Collection (BCC)
Requires:       %{name} = %{version}-%{release}
BuildArch:      noarch

%description -n python3-%{name}
Python3 bindings for BPF Compiler Collection (BCC)


%if %{with lua}
%package lua
Summary:        Standalone tool to run BCC tracers written in Lua
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description lua
Standalone tool to run BCC tracers written in Lua
%endif


%package tools
Summary:        Command line tools for BPF Compiler Collection (BCC)
Requires:       bcc = %{version}-%{release}
Requires:       python3-%{name} = %{version}-%{release}
Requires:       python3-netaddr

%description tools
Command line tools for BPF Compiler Collection (BCC)

%if %{with libbpf_tools}
%package -n libbpf-tools
Summary:        Command line libbpf tools for BPF Compiler Collection (BCC)
BuildRequires:  bpftool

%description -n libbpf-tools
Command line libbpf tools for BPF Compiler Collection (BCC)
%endif

%prep
%autosetup -p1


%build
%cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo \
       -DREVISION_LAST=%{version} -DREVISION=%{version} -DPYTHON_CMD=python3 \
       -DCMAKE_USE_LIBBPF_PACKAGE:BOOL=TRUE \
       %{?with_llvm_shared:-DENABLE_LLVM_SHARED=1}
%cmake_build

# It was discussed and agreed to package libbpf-tools with
# 'bpf-' prefix (https://github.com/iovisor/bcc/pull/3263)
# Installing libbpf-tools binaries in temp directory and
# renaming them in there and the install code will just
# take them.
%if %{with libbpf_tools}
pushd libbpf-tools;
make BPFTOOL=bpftool LIBBPF_OBJ=%{_libdir}/libbpf.a CFLAGS="%{optflags}" LDFLAGS="%{build_ldflags}"
make DESTDIR=./tmp-install prefix= install
(
    cd tmp-install/bin
    for file in *; do
        mv $file bpf-$file
    done
    # now fix the broken symlinks
    for file in `find . -type l`; do
        dest=$(readlink "$file")
        ln -s -f bpf-$dest $file
    done
)
popd
%endif

%install
%cmake_install

# Fix python shebangs
find %{buildroot}%{_datadir}/%{name}/{tools,examples} -type f -exec \
  sed -i -e '1s=^#!/usr/bin/python\([0-9.]\+\)\?$=#!%{__python3}=' \
         -e '1s=^#!/usr/bin/env python\([0-9.]\+\)\?$=#!%{__python3}=' \
         -e '1s=^#!/usr/bin/env bcc-lua$=#!/usr/bin/bcc-lua=' {} \;

# Move man pages to the right location
mkdir -p %{buildroot}%{_mandir}
mv %{buildroot}%{_datadir}/%{name}/man/* %{buildroot}%{_mandir}/
# Avoid conflict with other manpages
# https://bugzilla.redhat.com/show_bug.cgi?id=1517408
for i in `find %{buildroot}%{_mandir} -name "*.gz"`; do
  tname=$(basename $i)
  rename $tname %{name}-$tname $i
done
mkdir -p %{buildroot}%{_docdir}/%{name}
mv %{buildroot}%{_datadir}/%{name}/examples %{buildroot}%{_docdir}/%{name}/

# Delete old tools we don't want to ship
rm -rf %{buildroot}%{_datadir}/%{name}/tools/old/

# We cannot run the test suit since it requires root and it makes changes to
# the machine (e.g, IP address)
#%check

%if %{with libbpf_tools}
mkdir -p %{buildroot}/%{_sbindir}
# We cannot use `install` because some of the tools are symlinks and `install`
# follows those. Since all the tools already have the correct permissions set,
# we just need to copy them to the right place while preserving those
cp -a libbpf-tools/tmp-install/bin/* %{buildroot}/%{_sbindir}/
%endif

%ldconfig_scriptlets

%files
%doc README.md
%license LICENSE.txt
%{_libdir}/lib%{name}.so.*
%{_libdir}/libbcc_bpf.so.*

%files devel
%exclude %{_libdir}/lib%{name}*.a
%exclude %{_libdir}/lib%{name}*.la
%{_libdir}/lib%{name}.so
%{_libdir}/libbcc_bpf.so
%{_libdir}/pkgconfig/lib%{name}.pc
%{_includedir}/%{name}/

%files -n python3-%{name}
%{python3_sitelib}/%{name}*

%files doc
%dir %{_docdir}/%{name}
%doc %{_docdir}/%{name}/examples/

%files tools
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/tools/
%{_datadir}/%{name}/introspection/
%if 0%{?rhel} > 0
# inject relies on BPF_KPROBE_OVERRIDE which is not set on RHEL
%exclude %{_datadir}/%{name}/tools/inject
%exclude %{_datadir}/%{name}/tools/doc/inject_example.txt
%exclude %{_mandir}/man8/bcc-inject.8.gz
# Neither btrfs nor zfs are available on RHEL
%exclude %{_datadir}/%{name}/tools/btrfs*
%exclude %{_datadir}/%{name}/tools/doc/btrfs*
%exclude %{_mandir}/man8/bcc-btrfs*
%exclude %{_datadir}/%{name}/tools/zfs*
%exclude %{_datadir}/%{name}/tools/doc/zfs*
%exclude %{_mandir}/man8/bcc-zfs*
# criticalstat relies on CONFIG_PREEMPTIRQ_EVENTS which is disabled on RHEL
%exclude %{_datadir}/%{name}/tools/criticalstat
%exclude %{_datadir}/%{name}/tools/doc/criticalstat_example.txt
%exclude %{_mandir}/man8/bcc-criticalstat.8.gz
%endif
%{_mandir}/man8/*

%if %{with lua}
%files lua
%{_bindir}/bcc-lua
%endif

%if %{with libbpf_tools}
%files -n libbpf-tools
%{_sbindir}/bpf-*
%endif

%changelog
* Thu Jan 05 2023 Jerome Marchand <jmarchan@redhat.com> - 0.25.0-2
- Rebuild for libbpf 1.0

* Tue Dec 20 2022 Jerome Marchand <jmarchan@redhat.com> - 0.25.0-1
- Rebase to v0.25.0
- Misc documentation and man pages fixes

* Tue Aug 23 2022 Jerome Marchand <jmarchan@redhat.com> - 0.24.1-4
- Fix mdflush tool (rhbz#2108001)

* Fri Jul 01 2022 Jerome Marchand <jmarchan@redhat.com> - 0.24.1-3
- Rebuild for libbpf 0.6.0

* Wed May 18 2022 Jerome Marchand <jmarchan@redhat.com> - 0.24.1-2
- Rebuild (previous build failed with UNKNOWN_KOJI_ERROR)

* Thu Mar 24 2022 Jerome Marchand <jmarchan@redhat.com> - 0.24.0-1
- Rebase to v0.24.0
- Fix cmake build

* Fri Feb 25 2022 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-10
- Remove deprecated python_provides macro (needed for gating)

* Thu Feb 24 2022 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-9
- Fix bio tools (rhbz#2039595)

* Mon Nov 22 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-8
- Rebuild for LLVM 13

* Thu Oct 14 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-7
- Sync with latest libbpf (fixes BPF_F_BROADCAST breakages of rhbz#1992430)
- Fix cpudist, mdflush, readahead and threadsnoop (rhbz#1992430)
- Handle the renaming of task_struct_>state field
- Drop tools that relies on features disabled on RHEL

* Mon Aug 09 2021 Mohan Boddu <mboddu@redhat.com> - 0.20.0-6
- Rebuilt for IMA sigs, glibc 2.34, aarch64 flags
  Related: rhbz#1991688

* Tue Aug 03 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-5
- Add gating

* Mon Jul 26 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-4
- Don't require bcc-tools by default (#1967550)
- Add explicit bcc requirement to bcc-tools
- Build bcc from standard sources

* Wed Jun 02 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-3
- Don't ignore LDFLAGS for libbpf-tools

* Wed Jun 02 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-2
- Don't override cflags for libbpf-tools

* Thu May 27 2021 Jerome Marchand <jmarchan@redhat.com> - 0.20.0-1
- Rebase to bcc 0.20.0

* Thu May 13 2021 Tom Stellard <tstellar@redhat.com> - 0.18.0-6
- Rebuild for LLVM 12

* Thu Apr 15 2021 Mohan Boddu <mboddu@redhat.com> - 0.18.0-5
- Rebuilt for RHEL 9 BETA on Apr 15th 2021. Related: rhbz#1947937

* Thu Feb 18 2021 Jerome Marchand <jmarchan@redhat.com> - 0.18.0-4
- Disable lua for RHEL

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.18.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Jan 22 2021 Tom Stellard <tstellar@redhat.com> - 0.18.0-2
- Rebuild for clang-11.1.0

* Tue Jan  5 15:08:26 CET 2021 Rafael dos Santos <rdossant@redhat.com> - 0.18.0-1
- Rebase to latest upstream (#1912875)

* Fri Oct 30 11:25:46 CET 2020 Rafael dos Santos <rdossant@redhat.com> - 0.17.0-1
- Rebase to latest upstream (#1871417)

* Mon Oct 12 2020 Jerome Marchand <jmarchan@redhat.com> - 0.16.0.3
- Rebuild for LLVM 11.0.0-rc6

* Fri Aug 28 2020 Rafael dos Santos <rdossant@redhat.com> - 0.16.0-2
- Enable build for armv7hl

* Sun Aug 23 2020 Rafael dos Santos <rdossant@redhat.com> - 0.16.0-1
- Rebase to latest upstream (#1871417)

* Tue Aug 04 2020 Rafael dos Santos <rdossant@redhat.com> - 0.15.0-6
- Fix build with cmake (#1863243)

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.15.0-5
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.15.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Thu Jul 09 2020 Tom Stellard <tstellar@redhat.com> - 0.15.0-3
- Drop llvm-static dependency
- https://docs.fedoraproject.org/en-US/packaging-guidelines/#_statically_linking_executables

* Thu Jul 02 2020 Rafael dos Santos <rdossant@redhat.com> - 0.15.0-2
- Reinstate a function needed by bpftrace

* Tue Jun 23 2020 Rafael dos Santos <rdossant@redhat.com> - 0.15.0-1
- Rebase to latest upstream version (#1849239)

* Tue May 26 2020 Miro Hrončok <mhroncok@redhat.com> - 0.14.0-2
- Rebuilt for Python 3.9

* Tue Apr 21 2020 Rafael dos Santos <rdossant@redhat.com> - 0.14.0-1
- Rebase to latest upstream version (#1826281)

* Wed Feb 26 2020 Rafael dos Santos <rdossant@redhat.com> - 0.13.0-1
- Rebase to latest upstream version (#1805072)

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.12.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Mon Jan 06 2020 Tom Stellard <tstellar@redhat.com> - 0.12.0-2
- Link against libclang-cpp.so
- https://fedoraproject.org/wiki/Changes/Stop-Shipping-Individual-Component-Libraries-In-clang-lib-Package

* Tue Dec 17 2019 Rafael dos Santos <rdossant@redhat.com> - 0.12.0-1
- Rebase to latest upstream version (#1758417)

* Thu Dec 05 2019 Jiri Olsa <jolsa@redhat.com> - 0.11.0-2
- Add libbpf support

* Fri Oct 04 2019 Rafael dos Santos <rdossant@redhat.com> - 0.11.0-1
- Rebase to latest upstream version (#1758417)

* Thu Oct 03 2019 Miro Hrončok <mhroncok@redhat.com> - 0.10.0-4
- Rebuilt for Python 3.8.0rc1 (#1748018)

* Mon Aug 19 2019 Miro Hrončok <mhroncok@redhat.com> - 0.10.0-3
- Rebuilt for Python 3.8

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.10.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Wed May 29 2019 Rafael dos Santos <rdossant@redhat.com> - 0.10.0-1
- Rebase to latest upstream version (#1714902)

* Thu Apr 25 2019 Rafael dos Santos <rdossant@redhat.com> - 0.9.0-1
- Rebase to latest upstream version (#1686626)
- Rename libbpf header to libbcc_bpf

* Mon Apr 22 2019 Neal Gompa <ngompa@datto.com> - 0.8.0-5
- Make the Python 3 bindings package noarch
- Small cleanups to the spec

* Tue Mar 19 2019 Rafael dos Santos <rdossant@redhat.com> - 0.8.0-4
- Add s390x support (#1679310)

* Wed Feb 20 2019 Rafael dos Santos <rdossant@redhat.com> - 0.8.0-3
- Add aarch64 support (#1679310)

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Jan 17 2019 Rafael dos Santos <rdossant@redhat.com> - 0.8.0-1
- Rebase to new released version

* Thu Nov 01 2018 Rafael dos Santos <rdossant@redhat.com> - 0.7.0-4
- Fix attaching to usdt probes (#1634684)

* Mon Oct 22 2018 Rafael dos Santos <rdossant@redhat.com> - 0.7.0-3
- Fix encoding of non-utf8 characters (#1516678)
- Fix str-bytes conversion in killsnoop (#1637515)

* Sat Oct 06 2018 Rafael dos Santos <rdossant@redhat.com> - 0.7.0-2
- Fix str/bytes conversion in uflow (#1636293)

* Tue Sep 25 2018 Rafael Fonseca <r4f4rfs@gmail.com> - 0.7.0-1
- Rebase to new released version

* Wed Aug 22 2018 Rafael Fonseca <r4f4rfs@gmail.com> - 0.6.1-2
- Fix typo when mangling shebangs.

* Thu Aug 16 2018 Rafael Fonseca <r4f4rfs@gmail.com> - 0.6.1-1
- Rebase to new released version (#1609485)

* Thu Jul 12 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.6.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Tue Jun 19 2018 Miro Hrončok <mhroncok@redhat.com> - 0.6.0-2
- Rebuilt for Python 3.7

* Mon Jun 18 2018 Rafael dos Santos <rdossant@redhat.com> - 0.6.0-1
- Rebase to new released version (#1591989)

* Thu Apr 05 2018 Rafael Santos <rdossant@redhat.com> - 0.5.0-4
- Resolves #1555627 - fix compilation error with latest llvm/clang

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.5.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Fri Feb 02 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.5.0-2
- Switch to %%ldconfig_scriptlets

* Wed Jan 03 2018 Rafael Santos <rdossant@redhat.com> - 0.5.0-1
- Rebase to new released version

* Thu Nov 16 2017 Rafael Santos <rdossant@redhat.com> - 0.4.0-4
- Resolves #1517408 - avoid conflict with other manpages

* Thu Nov 02 2017 Rafael Santos <rdossant@redhat.com> - 0.4.0-3
- Use weak deps to not require lua subpkg on ppc64(le)

* Wed Nov 01 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.4.0-2
- Rebuild for LLVM5

* Wed Nov 01 2017 Rafael Fonseca <rdossant@redhat.com> - 0.4.0-1
- Resolves #1460482 - rebase to new release
- Resolves #1505506 - add support for LLVM 5.0
- Resolves #1460482 - BPF module compilation issue
- Partially address #1479990 - location of man pages
- Enable ppc64(le) support without lua
- Soname versioning for libbpf by ignatenkobrain

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Thu Mar 30 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.3.0-2
- Rebuild for LLVM4
- Trivial fixes in spec

* Fri Mar 10 2017 Rafael Fonseca <rdossant@redhat.com> - 0.3.0-1
- Rebase to new release.

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Tue Jan 10 2017 Rafael Fonseca <rdossant@redhat.com> - 0.2.0-2
- Fix typo

* Tue Nov 29 2016 Rafael Fonseca <rdossant@redhat.com> - 0.2.0-1
- Initial import
