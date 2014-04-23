import os
import subprocess
from StringIO import StringIO
from tempfile import mkdtemp

def get_repo_node(env, repo_name, node):
    try:
        from tracopt.versioncontrol.git.PyGIT import GitError
    except ImportError: ## Pre-1.0 Trac
        from tracext.git.PyGIT import GitError
    from trac.core import TracError
    try:
        repo = env.get_repository(reponame=repo_name)
        if not repo:
            retunr None
        return repo.get_node(node)
    except GitError:
        raise TracError("Error reading Git files at %s; check your repository path (for repo %s) and file permissions" % (node, repo_name))


def read_config(env,fp):
    repos = {}
    this_repo = None
    groups = {}
    inverse_groups = {}
    info = {}
    for line in fp:
        line = line.strip()
        if line.startswith("@"): ## we assume that groups definitions preceed repo definitions!
            env.log.debug("%%% group section")
            group, users = line.split('=')
            group = group.strip()
            users = [i.strip() for i in users.split()]
            if group in groups:
                env.log.debug("add: member(s) %r to %r", users, group)
                groups[group].extend(users)
            else:
                env.log.debug("new: member(s) %r to %r", users, group)
                groups[group] = list(users)
            for user in users:
                if user in inverse_groups:
                    env.log.debug("add: group %r to %r", group, user)
                    inverse_groups[user].extend([group])
                else:
                    env.log.debug("new: group %r to %r", group, user)
                    inverse_groups[user] = list([group])
        elif line.startswith("repo"):
            env.log.debug("%%% repo section")
            if this_repo is not None and len(info) > 0:
                repos[this_repo] = info
            this_repo = line[len("repo"):].strip()
            info = {}
        elif '=' in line:
            env.log.debug("%%% user section")
            perms, users = line.split("=")
            env.log.debug("perms: %r, targets: %r", perms, users)
            perms = perms.strip().upper()
            users = [i.strip() for i in users.split()]
            for perm in perms:
                if perm in info:
                    env.log.debug("add: granting %r to %r", perm, users)
                    info[perm].extend(users)
                else:
                    env.log.debug("new: granting %r to %r", perm, users)
                    info[perm] = list(users) ## Copy it!

    if this_repo is not None and len(info) > 0:
        repos[this_repo] = info

    fp.close()
    return repos, groups, inverse_groups


def to_string(repos, groups):

    def _sort(perms):
        tail = []
        ## Ensure the + goes last
        if '+' in perms:
            perms = perms.replace("+", '')
            tail.append("+")
        perms = sorted(perms)
        perms.extend(tail)
        return ''.join(perms)

    fp = StringIO()
    for group in groups:
        fp.write("%s\t=" % group)
        for member in groups[group]:
            fp.write(" %s" % member)
        fp.write("\n")
    fp.write("\n")

    for repo in sorted(repos):
        fp.write("repo\t%s\n" % repo)

        ## Combine permissions
        perms = repos[repo]
        transposed = {}
        for perm in perms:
            for user in perms[perm]:
                if user in transposed:
                    transposed[user] += perm
                    transposed[user] = _sort(transposed[user])
                else:
                    transposed[user] = perm


        detransposed = {}
        for user in transposed:
            if transposed[user] in detransposed:
                detransposed[transposed[user]].append(user)
                detransposed[transposed[user]] = sorted(detransposed[transposed[user]])
            else:
                detransposed[transposed[user]] = [user]

        for permset in sorted(detransposed):
            fp.write("\t%s\t=\t%s\n" % (permset, ' '.join(detransposed[permset])))

        fp.write("\n")
    fp.seek(0)
    return fp.read()

def save_file(repo_path, file_path, contents, msg):
    tempdir = mkdtemp()
    subprocess.check_call(['git', 'clone', repo_path, tempdir])
    fp = open(os.path.join(tempdir, file_path), 'w')
    fp.write(contents)
    fp.close()
    subprocess.check_call(['git', 'add', file_path], cwd=tempdir)
    subprocess.check_call(['git', 'commit', '-m', msg], cwd=tempdir)
    subprocess.check_call(['git', 'push'], cwd=tempdir)

def remove_files(repo_path, file_paths, msg):
    tempdir = mkdtemp()
    subprocess.check_call(['git', 'clone', repo_path, tempdir])
    for file_path in file_paths:
        subprocess.check_call(['git', 'rm', file_path], cwd=tempdir)
    subprocess.check_call(['git', 'commit', '-m', msg], cwd=tempdir)
    subprocess.check_call(['git', 'push'], cwd=tempdir)
    
